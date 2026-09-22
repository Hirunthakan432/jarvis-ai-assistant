package com.hirunthakan.jarvis;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.media.AudioManager;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import androidx.work.Data;
import androidx.work.ExistingWorkPolicy;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkInfo;
import androidx.work.WorkManager;
import org.json.JSONArray;
import org.json.JSONObject;
import java.lang.ref.WeakReference;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

/** In-process bridge only. Not exported, not JavaScript, and not a service endpoint. */
public final class NativeBridge {
    private final Context context;
    private final Handler main = new Handler(Looper.getMainLooper());
    private volatile WeakReference<Activity> foreground = new WeakReference<>(null);
    private final AtomicLong generation = new AtomicLong();
    private final ProviderTransport transport;
    public NativeBridge(Context context) {
        this.context = context.getApplicationContext();
        transport = new ProviderTransport(new SecretStore(this.context));
    }
    public void attach(Activity activity) { foreground = new WeakReference<>(activity); }
    public void detach(Activity activity) { if (foreground.get() == activity) foreground.clear(); stop(); }
    public void stop() { generation.incrementAndGet(); transport.cancel(); }
    public String request(String provider, String model, String payload) { return transport.request(provider, model, payload); }
    public String apps() {
        JSONObject result = new JSONObject();
        PackageManager manager = context.getPackageManager();
        Intent intent = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        try {
            List<ResolveInfo> launchers = manager.queryIntentActivities(intent, 0);
            // Package aliases are always unique. Labels are admitted only when unambiguous.
            java.util.Map<String, Integer> counts = new java.util.HashMap<>();
            for (ResolveInfo info : launchers) {
                String label = info.loadLabel(manager).toString().trim().toLowerCase(Locale.ROOT);
                counts.put(label, counts.getOrDefault(label, 0) + 1);
                result.put(info.activityInfo.packageName, info.activityInfo.packageName);
            }
            for (ResolveInfo info : launchers) {
                String label = info.loadLabel(manager).toString().trim().toLowerCase(Locale.ROOT);
                if (!label.isEmpty() && counts.get(label) == 1 && !result.has(label)) result.put(label, info.activityInfo.packageName);
            }
        } catch (Exception ignored) { /* Empty list is safe if a profile denies visibility. */ }
        return result.toString();
    }
    private Activity activity() {
        Activity activity = foreground.get();
        if (activity == null || activity.isFinishing() || activity.isDestroyed())
            throw new IllegalStateException("Return to Jarvis and request the action again.");
        return activity;
    }
    private void permission(String value) {
        if (context.checkSelfPermission(value) != PackageManager.PERMISSION_GRANTED)
            throw new SecurityException();
    }
    private void notifications() {
        if (!ReminderWorker.notificationsAllowed(context)) throw new SecurityException();
    }
    static boolean validUrl(String value) {
        try {
            java.net.URI uri = new java.net.URI(value);
            return ("https".equals(uri.getScheme()) || "http".equals(uri.getScheme()))
                && uri.getHost() != null && uri.getUserInfo() == null;
        } catch (Exception invalid) { return false; }
    }
    public String execute(String name, String encoded) {
        try {
            JSONObject args = new JSONObject(encoded);
            long ticket = generation.get();
            Object result;
            if (name.equals("list_reminders")) {
                JSONArray rows = new JSONArray();
                for (WorkInfo info : WorkManager.getInstance(context).getWorkInfosByTag("jarvis-reminder").get(5, TimeUnit.SECONDS)) {
                    if (!info.getState().isFinished()) {
                        for (String tag : info.getTags()) if (tag.startsWith("reminder-id:"))
                            rows.put(new JSONObject().put("id", Integer.parseInt(tag.substring(12))).put("state", info.getState().name()));
                    }
                }
                result = rows;
            } else {
                FutureTask<Object> task = new FutureTask<>(() -> {
                    if (ticket != generation.get()) throw new IllegalStateException();
                    return dispatch(name, args);
                });
                if (Looper.myLooper() == Looper.getMainLooper()) task.run(); else main.post(task);
                try { result = task.get(5, TimeUnit.SECONDS); }
                finally { task.cancel(false); } // A timed-out queued effect must never run later.
            }
            return new JSONObject().put("ok", true).put("result", result).toString();
        } catch (Exception error) {
            Throwable cause = error.getCause() == null ? error : error.getCause();
            String detail = cause instanceof SecurityException
                ? "Permission denied. Grant the needed permission in Jarvis settings, then request and confirm again."
                : "Android action unavailable. Check hardware, foreground app, permission and target; inspect the result before retrying.";
            try { return new JSONObject().put("ok", false).put("error", detail).toString(); }
            catch (Exception ignored) { return "{\"ok\":false}"; }
        }
    }
    @android.annotation.SuppressLint("MissingPermission") // Torch checks CAMERA; notifications recheck inside notify.
    private Object dispatch(String name, JSONObject args) throws Exception {
        AudioManager audio = context.getSystemService(AudioManager.class);
        switch (name) {
            case "battery_info": {
                Intent battery = context.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
                if (battery == null) throw new IllegalStateException();
                int scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
                int level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
                return new JSONObject().put("percent", scale > 0 && level >= 0 ? 100 * level / scale : JSONObject.NULL)
                    .put("plugged_in", battery.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) != 0);
            }
            case "computer_status":
            case "device_info": return new JSONObject().put("platform", "Android").put("manufacturer", Build.MANUFACTURER)
                .put("model", Build.MODEL).put("android", Build.VERSION.RELEASE).put("api", Build.VERSION.SDK_INT);
            case "network_info": {
                ConnectivityManager manager = context.getSystemService(ConnectivityManager.class);
                Network network = manager.getActiveNetwork();
                NetworkCapabilities caps = manager.getNetworkCapabilities(network);
                return new JSONObject().put("connected", caps != null)
                    .put("internet_validated", caps != null && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED))
                    .put("wifi", caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI))
                    .put("cellular", caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR))
                    .put("vpn", caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN));
            }
            case "get_volume": return new JSONObject().put("percent", Math.round(100f * audio.getStreamVolume(AudioManager.STREAM_MUSIC)
                / Math.max(1, audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC))));
            default: activity(); // Every effect requires a visible, resumed UI.
        }
        switch (name) {
            case "open_app": {
                String target = args.getString("package");
                if (!new JSONObject(apps()).has(target)) throw new IllegalArgumentException();
                Intent launch = context.getPackageManager().getLaunchIntentForPackage(target);
                if (launch == null) throw new IllegalStateException();
                activity().startActivity(launch);
                return "Application launch requested.";
            }
            case "open_url": {
                String url = args.getString("url");
                if (!validUrl(url)) throw new IllegalArgumentException();
                activity().startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)).addCategory(Intent.CATEGORY_BROWSABLE));
                return "URL opened in the selected application.";
            }
            case "share_text":
                activity().startActivity(Intent.createChooser(new Intent(Intent.ACTION_SEND).setType("text/plain")
                    .putExtra(Intent.EXTRA_TEXT, args.getString("text")), "Share through Android"));
                return "Sharesheet opened. Select a recipient and send in the chosen app.";
            case "flashlight": {
                permission(Manifest.permission.CAMERA);
                String state = args.getString("state");
                if (!state.equals("on") && !state.equals("off")) throw new IllegalArgumentException();
                CameraManager manager = context.getSystemService(CameraManager.class);
                for (String id : manager.getCameraIdList()) {
                    if (Boolean.TRUE.equals(manager.getCameraCharacteristics(id).get(CameraCharacteristics.FLASH_INFO_AVAILABLE))) {
                        manager.setTorchMode(id, state.equals("on"));
                        return "Flashlight " + state + ".";
                    }
                }
                throw new IllegalStateException();
            }
            case "set_volume": {
                int percent = args.getInt("percent");
                if (percent < 0 || percent > 100) throw new IllegalArgumentException();
                audio.setStreamVolume(AudioManager.STREAM_MUSIC,
                    Math.round(audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC) * percent / 100f), AudioManager.FLAG_SHOW_UI);
                return "Media volume change requested.";
            }
            case "media_control": {
                String action = args.getString("action");
                if (action.equals("volume_up") || action.equals("volume_down") || action.equals("mute")) {
                    int direction = action.equals("mute") ? AudioManager.ADJUST_TOGGLE_MUTE :
                        action.equals("volume_up") ? AudioManager.ADJUST_RAISE : AudioManager.ADJUST_LOWER;
                    audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, direction, AudioManager.FLAG_SHOW_UI);
                } else {
                    int key;
                    switch (action) {
                        case "play_pause": key = KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE; break;
                        case "next": key = KeyEvent.KEYCODE_MEDIA_NEXT; break;
                        case "previous": key = KeyEvent.KEYCODE_MEDIA_PREVIOUS; break;
                        default: throw new IllegalArgumentException();
                    }
                    audio.dispatchMediaKeyEvent(new KeyEvent(KeyEvent.ACTION_DOWN, key));
                    audio.dispatchMediaKeyEvent(new KeyEvent(KeyEvent.ACTION_UP, key));
                }
                return "Media request sent; the active media app decides whether to handle it.";
            }
            case "notify": notifications(); ReminderWorker.notify(context, 0, args.getString("text")); return "Notification posted.";
            case "add_reminder": {
                notifications();
                int delay = args.getInt("delay_seconds");
                if (delay < 1 || delay > 31536000 || args.optInt("repeat_seconds", 0) != 0) throw new IllegalArgumentException();
                SharedPreferences prefs = context.getSharedPreferences("reminder_ids", Context.MODE_PRIVATE);
                int id = prefs.getInt("next", 1);
                if (id == Integer.MAX_VALUE || !prefs.edit().putInt("next", id + 1).commit()) throw new IllegalStateException();
                OneTimeWorkRequest work = new OneTimeWorkRequest.Builder(ReminderWorker.class)
                    .setInputData(new Data.Builder().putString("text", args.getString("text")).putInt("id", id).build())
                    .setInitialDelay(delay, TimeUnit.SECONDS).addTag("jarvis-reminder").addTag("reminder-id:" + id).build();
                WorkManager.getInstance(context).enqueueUniqueWork("reminder-" + id, ExistingWorkPolicy.KEEP, work);
                return "Reminder #" + id + " submitted to Android. Delivery may be delayed by battery restrictions.";
            }
            case "cancel_reminder":
                WorkManager.getInstance(context).cancelUniqueWork("reminder-" + args.getInt("id"));
                return "Reminder cancellation requested.";
            default: throw new IllegalArgumentException();
        }
    }
}
