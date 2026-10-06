package com.hirunthakan.jarvis;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

/** OS-scheduled, one-time reminders survive process death and ordinary reboot. */
public final class ReminderWorker extends Worker {
    static final String CHANNEL = "jarvis_reminders";
    public ReminderWorker(@NonNull Context context, @NonNull WorkerParameters params) { super(context, params); }
    static boolean notificationsAllowed(Context context) {
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        NotificationChannel channel = manager.getNotificationChannel(CHANNEL);
        return manager.areNotificationsEnabled() && (channel == null || channel.getImportance() != NotificationManager.IMPORTANCE_NONE)
            && (Build.VERSION.SDK_INT < 33 || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED);
    }
    @android.annotation.SuppressLint("MissingPermission") // Checked immediately before notify.
    static void notify(Context context, int id, String text) {
        if (!notificationsAllowed(context)) throw new SecurityException();
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel(CHANNEL, "Jarvis reminders", NotificationManager.IMPORTANCE_DEFAULT));
        manager.notify(id, new Notification.Builder(context, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("Jarvis")
            .setContentText(text).setStyle(new Notification.BigTextStyle().bigText(text))
            .setVisibility(Notification.VISIBILITY_PRIVATE).setAutoCancel(true).build());
    }
    @NonNull @Override public Result doWork() {
        Context context = getApplicationContext();
        if (!notificationsAllowed(context)) return Result.failure();
        int id = getInputData().getInt("id", 0);
        String text = getInputData().getString("text");
        if (id < 1 || text == null) return Result.failure();
        try { notify(context, id, text); return Result.success(); }
        catch (SecurityException denied) { return Result.failure(); }
    }
}
