package com.hirunthakan.jarvis;

import android.app.Application;
import androidx.annotation.NonNull;
import androidx.lifecycle.AndroidViewModel;
import androidx.lifecycle.MutableLiveData;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/** A single command executor serializes Python state, retained across rotation. */
public final class JarvisViewModel extends AndroidViewModel {
    public final NativeBridge bridge;
    public final MutableLiveData<String> transcript = new MutableLiveData<>("");
    public final MutableLiveData<String> status = new MutableLiveData<>("Starting local core…");
    public final MutableLiveData<Boolean> working = new MutableLiveData<>(true);
    public final MutableLiveData<JSONArray> pending = new MutableLiveData<>(new JSONArray());
    public final MutableLiveData<String> speech = new MutableLiveData<>("");
    private final ExecutorService commands = Executors.newSingleThreadExecutor();
    private final ExecutorService cancellations = Executors.newSingleThreadExecutor();
    private final AtomicBoolean busy = new AtomicBoolean(true);
    private volatile PyObject runtime;
    private final StringBuilder log = new StringBuilder();
    public JarvisViewModel(@NonNull Application application) {
        super(application);
        bridge = new NativeBridge(application);
        commands.execute(this::initialize);
    }
    private void initialize() {
        try {
            if (!Python.isStarted()) Python.start(new AndroidPlatform(getApplication()));
            String options = getApplication().getSharedPreferences("settings", 0).getString("options", "{}");
            runtime = Python.getInstance().getModule("mobile.runtime").callAttr("Runtime",
                getApplication().getFilesDir().getAbsolutePath() + "/jarvis", bridge, options);
            if (log.length() == 0) {
                JSONArray history = new JSONArray(runtime.callAttr("history").toString());
                for (int i = 0; i < history.length(); i++) {
                    JSONObject turn = history.getJSONObject(i);
                    append((turn.getString("role").equals("user") ? "You: " : "Jarvis: ") + turn.getString("content"));
                }
            }
            status.postValue("Ready · local commands first · AI " + (new JSONObject(options).optBoolean("ai_enabled") ? "enabled" : "off"));
        } catch (Exception error) {
            runtime = null;
            status.postValue("Core failed to start. Check settings and restart Jarvis. No device actions are available.");
        } finally { busy.set(false); working.postValue(false); }
    }
    public void reload() {
        if (!busy.compareAndSet(false, true)) return;
        working.setValue(true);
        stop();
        commands.execute(this::initialize);
    }
    private synchronized void append(String text) {
        log.append(text).append("\n\n");
        if (log.length() > 60000) log.delete(0, log.length() - 60000);
        transcript.postValue(log.toString());
    }
    public void send(String text, String source, String utteranceId) {
        if (text.trim().isEmpty() || !busy.compareAndSet(false, true)) return;
        if (runtime == null) { busy.set(false); return; }
        working.setValue(true);
        append("You: " + text);
        commands.execute(() -> {
            try {
                JSONObject response = new JSONObject(runtime.callAttr("chat", text, source, utteranceId).toString());
                String reply = response.getString("reply");
                append("Jarvis: " + reply);
                status.postValue(response.getString("mode") + " · AI " + (response.getBoolean("ai_enabled") ? "enabled" : "off")
                    + " · provider: " + response.getString("provider_status"));
                pending.postValue(response.getJSONArray("pending"));
                speech.postValue(reply);
            } catch (Exception error) {
                append("Jarvis: Command failed. No exception details or credentials were logged. Check settings and try again.");
                pending.postValue(new JSONArray());
            } finally { busy.set(false); working.postValue(false); }
        });
    }
    public void stop() {
        bridge.stop();
        pending.postValue(new JSONArray());
        PyObject current = runtime;
        if (current != null) cancellations.execute(() -> current.callAttr("stop"));
    }
    @Override protected void onCleared() {
        stop(); commands.shutdownNow(); cancellations.shutdown(); super.onCleared();
    }
}
