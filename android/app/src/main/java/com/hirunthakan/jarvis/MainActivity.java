package com.hirunthakan.jarvis;

import android.Manifest;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.Voice;
import android.text.InputType;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.widget.*;
import androidx.activity.ComponentActivity;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.lifecycle.ViewModelProvider;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.Locale;
import java.util.UUID;

/** Native accessible views; no WebView or remotely loaded UI. */
public final class MainActivity extends ComponentActivity {
    private JarvisViewModel model;
    private TextView permissions, response, connection;
    private EditText input;
    private LinearLayout approvals;
    private Button microphone;
    private SpeechRecognizer recognizer;
    private TextToSpeech tts;
    private boolean ttsReady, listening;
    private String utterance;
    private final ActivityResultLauncher<String> permissionRequest = registerForActivityResult(
        new ActivityResultContracts.RequestPermission(), granted -> {
            updatePermissions();
            Toast.makeText(this, granted ? "Permission granted. Request the action again." :
                "Permission denied. Text commands remain available.", Toast.LENGTH_LONG).show();
        });
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        model = new ViewModelProvider(this).get(JarvisViewModel.class);
        LinearLayout root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL);
        int spacing = dp(12); root.setPadding(spacing, spacing, spacing, spacing);
        root.setBackgroundColor(0xfff4f7fc);
        ViewCompat.setOnApplyWindowInsetsListener(root, (view, insets) -> {
            androidx.core.graphics.Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.ime());
            view.setPadding(spacing + bars.left, spacing + bars.top, spacing + bars.right, spacing + bars.bottom);
            return insets;
        });
        TextView title = label("Jarvis", 26); root.addView(title);
        TextView status = label("Starting…", 14); root.addView(status);
        connection = label("", 13); root.addView(connection);
        connection.setText(connectivity());
        permissions = label("", 13); root.addView(permissions);
        LinearLayout toolbar = new LinearLayout(this);
        toolbar.addView(button("Settings", this::settings), weight());
        toolbar.addView(button("Permissions", this::permissionPanel), weight());
        toolbar.addView(button("Enable controls", () -> model.send("/control on", "text", null)), weight());
        root.addView(toolbar);
        ScrollView scroll = new ScrollView(this);
        response = label("Try battery status, device info, or /local.", 17); response.setTextIsSelectable(true);
        scroll.addView(response); root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        ScrollView approvalScroll = new ScrollView(this);
        approvals = new LinearLayout(this); approvals.setOrientation(LinearLayout.VERTICAL);
        approvalScroll.addView(approvals); root.addView(approvalScroll, new LinearLayout.LayoutParams(-1, dp(120)));
        input = new EditText(this); input.setHint("Type a command…"); input.setMaxLines(4);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        input.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(12000)});
        input.setImeOptions(EditorInfo.IME_ACTION_SEND);
        input.setOnEditorActionListener((v, action, event) -> { if (action == EditorInfo.IME_ACTION_SEND) { send(); return true; } return false; });
        root.addView(input);
        LinearLayout actions = new LinearLayout(this);
        Button send = button("Send", this::send); actions.addView(send, weight());
        microphone = button("Microphone", this::voice); actions.addView(microphone, weight());
        actions.addView(button("Stop", () -> { stopVoice(); model.stop(); if (tts != null) tts.stop(); }), weight());
        root.addView(actions); setContentView(root);
        model.transcript.observe(this, value -> { if (!value.isEmpty()) response.setText(value); scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN)); });
        model.status.observe(this, status::setText);
        model.working.observe(this, busy -> { send.setEnabled(!busy); microphone.setEnabled(!busy); input.setEnabled(!busy); });
        model.pending.observe(this, this::showApprovals);
        model.speech.observe(this, value -> {
            if (ttsReady && prefs().getBoolean("speak", false) && !value.isEmpty())
                tts.speak(value.substring(0, Math.min(value.length(), TextToSpeech.getMaxSpeechInputLength())), TextToSpeech.QUEUE_FLUSH, null, UUID.randomUUID().toString());
        });
        tts = new TextToSpeech(this, result -> {
            if (result == TextToSpeech.SUCCESS && tts != null && tts.getVoices() != null) {
                for (Voice candidate : tts.getVoices()) {
                    if (!candidate.isNetworkConnectionRequired() && candidate.getLocale().getLanguage().equals(Locale.getDefault().getLanguage())) {
                        ttsReady = tts.setVoice(candidate) == TextToSpeech.SUCCESS; break;
                    }
                }
            }
        });
        updatePermissions();
    }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private LinearLayout.LayoutParams weight() { return new LinearLayout.LayoutParams(0, -2, 1); }
    private TextView label(String text, int size) { TextView view = new TextView(this); view.setText(text); view.setTextSize(size); view.setPadding(0, dp(4), 0, dp(4)); return view; }
    private Button button(String name, Runnable action) { Button button = new Button(this); button.setText(name); button.setAllCaps(false); button.setMinHeight(dp(48)); button.setOnClickListener(v -> action.run()); return button; }
    private SharedPreferences prefs() { return getSharedPreferences("settings", MODE_PRIVATE); }
    private void send() { String text = input.getText().toString(); if (!text.trim().isEmpty()) { model.send(text, "text", null); input.setText(""); } }
    private void showApprovals(JSONArray rows) {
        approvals.removeAllViews();
        for (int index = 0; index < rows.length(); index++) {
            JSONObject row = rows.optJSONObject(index); if (row == null) continue;
            String token = row.optString("token");
            approvals.addView(label(row.optString("action") + ": " + row.optJSONObject("arguments"), 14));
            LinearLayout buttons = new LinearLayout(this);
            buttons.addView(button("Confirm", () -> model.send("/confirm " + token, "text", null)), weight());
            buttons.addView(button("Cancel", () -> model.send("/cancel " + token, "text", null)), weight());
            approvals.addView(buttons);
        }
    }
    private boolean granted(String permission) { return checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED; }
    private void updatePermissions() {
        if (permissions == null) return;
        permissions.setText("Mic: " + (granted(Manifest.permission.RECORD_AUDIO) ? "allowed" : "off") + " · Flashlight: " +
            (granted(Manifest.permission.CAMERA) ? "allowed" : "off") + " · Notifications: " + (ReminderWorker.notificationsAllowed(this) ? "allowed" : "off"));
    }
    private String connectivity() {
        try {
            JSONObject state = new JSONObject(model.bridge.execute("network_info", "{}")).getJSONObject("result");
            return state.optBoolean("internet_validated") ? "Internet available · local controls work offline" : "Offline or unvalidated network · local controls available";
        } catch (Exception error) { return "Connectivity unknown · local controls available"; }
    }
    private void ask(String permission, String reason) {
        if (granted(permission)) { Toast.makeText(this, "Already allowed", Toast.LENGTH_SHORT).show(); return; }
        new AlertDialog.Builder(this).setTitle("Android permission").setMessage(reason)
            .setNegativeButton("Cancel", null).setPositiveButton("Continue", (d, w) -> permissionRequest.launch(permission)).show();
    }
    private void permissionPanel() {
        String[] choices = {"Microphone for voice input", "Camera permission for flashlight only", "Notifications and reminders", "Open Android app settings"};
        new AlertDialog.Builder(this).setTitle("Optional permissions").setItems(choices, (d, which) -> {
            if (which == 0) ask(Manifest.permission.RECORD_AUDIO, "Jarvis listens only after you tap Microphone. Text input needs no microphone permission.");
            if (which == 1) ask(Manifest.permission.CAMERA, "Android requires camera permission for flashlight access. Jarvis does not capture photos.");
            if (which == 2) {
                if (Build.VERSION.SDK_INT >= 33) ask(Manifest.permission.POST_NOTIFICATIONS, "Allow Jarvis to show notifications and scheduled reminders.");
                else startActivity(new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName()));
            }
            if (which == 3) startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, android.net.Uri.parse("package:" + getPackageName())));
        }).show();
    }
    private void voice() {
        if (listening) { stopVoice(); return; }
        if (!granted(Manifest.permission.RECORD_AUDIO)) { ask(Manifest.permission.RECORD_AUDIO, "Allow microphone access for tap-to-talk commands."); return; }
        boolean local = Build.VERSION.SDK_INT >= 31 && SpeechRecognizer.isOnDeviceRecognitionAvailable(this);
        if (!local && !prefs().getBoolean("network_voice", false)) {
            new AlertDialog.Builder(this).setTitle("On-device speech unavailable").setMessage("Use text input, install an on-device speech service, or explicitly allow system speech recognition in Settings. System recognition may send audio to its provider.").setPositiveButton("OK", null).show(); return;
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this) && !local) { Toast.makeText(this, "No speech service installed", Toast.LENGTH_LONG).show(); return; }
        stopVoice(); if (tts != null) tts.stop();
        try {
        recognizer = local ? SpeechRecognizer.createOnDeviceSpeechRecognizer(this) : SpeechRecognizer.createSpeechRecognizer(this);
        utterance = UUID.randomUUID().toString(); final String recognitionId = utterance;
        recognizer.setRecognitionListener(new RecognitionListener() {
            public void onReadyForSpeech(Bundle b) { microphone.setText("Listening… tap to stop"); }
            public void onBeginningOfSpeech() {} public void onRmsChanged(float rms) {} public void onBufferReceived(byte[] b) {}
            public void onEndOfSpeech() { microphone.setText("Recognizing…"); }
            public void onError(int error) { if (!recognitionId.equals(utterance)) return; stopVoice(); Toast.makeText(MainActivity.this, "Speech unavailable (" + error + "). Try again or type.", Toast.LENGTH_LONG).show(); }
            public void onResults(Bundle results) {
                if (!recognitionId.equals(utterance)) return;
                ArrayList<String> words = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                stopVoice(); if (words != null && !words.isEmpty()) model.send(words.get(0), "voice", recognitionId);
            }
            public void onPartialResults(Bundle b) {} public void onEvent(int type, Bundle b) {}
        });
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
            .putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, local).putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false);
        listening = true; recognizer.startListening(intent);
        } catch (RuntimeException unavailable) { stopVoice(); Toast.makeText(this, "Speech unavailable. Check permission or type instead.", Toast.LENGTH_LONG).show(); }
    }
    private void stopVoice() { utterance = null; listening = false; if (recognizer != null) { recognizer.cancel(); recognizer.destroy(); recognizer = null; } if (microphone != null) microphone.setText("Microphone"); }
    private void settings() {
        if (Boolean.TRUE.equals(model.working.getValue())) { Toast.makeText(this, "Stop or finish the current request first", Toast.LENGTH_LONG).show(); return; }
        JSONObject existing; try { existing = new JSONObject(prefs().getString("options", "{}")); } catch (Exception error) { existing = new JSONObject(); }
        LinearLayout form = new LinearLayout(this); form.setOrientation(LinearLayout.VERTICAL); form.setPadding(dp(20), 0, dp(20), 0);
        CheckBox ai = new CheckBox(this); ai.setText("Enable AI for unmatched questions"); ai.setChecked(existing.optBoolean("ai_enabled")); form.addView(ai);
        Spinner provider = new Spinner(this); String[] providers = {"openai", "anthropic", "gemini", "ollama"};
        provider.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, providers));
        for (int i = 0; i < providers.length; i++) if (providers[i].equals(existing.optString("provider"))) provider.setSelection(i);
        form.addView(label("Provider", 14)); form.addView(provider);
        EditText name = new EditText(this); name.setHint("Model (blank = provider default)"); name.setText(existing.optString("model")); form.addView(name);
        EditText endpoint = new EditText(this); endpoint.setHint("Ollama trusted HTTPS LAN endpoint"); endpoint.setText(existing.optString("ollama_url", "https://127.0.0.1:11434")); form.addView(endpoint);
        EditText key = new EditText(this); key.setHint("API key (blank keeps existing key)"); key.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        key.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO); form.addView(key);
        CheckBox remove = new CheckBox(this); remove.setText("Delete selected provider key"); form.addView(remove);
        CheckBox onlineVoice = new CheckBox(this); onlineVoice.setText("Allow system speech when on-device speech is unavailable (may send audio online)"); onlineVoice.setChecked(prefs().getBoolean("network_voice", false)); form.addView(onlineVoice);
        CheckBox speak = new CheckBox(this); speak.setText("Speak replies using an installed offline voice"); speak.setChecked(prefs().getBoolean("speak", false)); form.addView(speak);
        form.addView(label("Cloud AI sends your question, conversation and approved memory to the selected provider. Keys are encrypted with Android Keystore. AI is optional. Ollama needs a separately hosted LAN server and trusted HTTPS.", 14));
        ScrollView scroll = new ScrollView(this); scroll.addView(form);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("Jarvis settings").setView(scroll).setNegativeButton("Cancel", null).setPositiveButton("Save", null).create();
        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            try {
                String chosen = provider.getSelectedItem().toString();
                String modelName = name.getText().toString().trim();
                String url = endpoint.getText().toString().trim();
                if (modelName.length() > 200 || (chosen.equals("ollama") && !url.startsWith("https://"))) throw new IllegalArgumentException();
                SecretStore store = new SecretStore(this);
                if (remove.isChecked()) store.put(chosen, "");
                else if (key.length() > 0) store.put(chosen, key.getText().toString().trim());
                JSONObject options = new JSONObject().put("provider", chosen).put("model", modelName)
                    .put("ollama_url", url).put("ai_enabled", ai.isChecked());
                if (!prefs().edit().putString("options", options.toString()).putBoolean("network_voice", onlineVoice.isChecked())
                    .putBoolean("speak", speak.isChecked()).commit()) throw new IllegalStateException();
                key.setText(""); model.reload(); dialog.dismiss();
                if (speak.isChecked() && !ttsReady) Toast.makeText(this, "Install an offline TTS voice in Android settings", Toast.LENGTH_LONG).show();
            } catch (Exception error) { Toast.makeText(this, "Could not save. Check model, HTTPS endpoint and secure storage.", Toast.LENGTH_LONG).show(); }
        }));
        dialog.show();
    }
    @Override protected void onResume() { super.onResume(); if (model != null) model.bridge.attach(this); updatePermissions(); if (connection != null) connection.setText(connectivity()); }
    @Override protected void onPause() { stopVoice(); if (tts != null) tts.stop(); if (model != null) { model.bridge.detach(this); model.stop(); } super.onPause(); }
    @Override protected void onDestroy() { if (tts != null) tts.shutdown(); super.onDestroy(); }
}
