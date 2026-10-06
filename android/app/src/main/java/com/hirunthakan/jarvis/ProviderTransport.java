package com.hirunthakan.jarvis;

import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.HttpsURLConnection;

/** Fixed provider destinations, bounded responses, no redirects, no secret logging. */
public final class ProviderTransport {
    private final SecretStore secrets;
    private volatile HttpsURLConnection active;
    public ProviderTransport(SecretStore secrets) { this.secrets = secrets; }
    public void cancel() { HttpsURLConnection c = active; if (c != null) c.disconnect(); }
    public String request(String provider, String model, String payload) {
        HttpsURLConnection connection = null;
        try {
            if (!model.matches("[A-Za-z0-9._:/-]{1,200}") || model.contains(".."))
                throw new IllegalArgumentException();
            String endpoint;
            switch (provider) {
                case "openai": endpoint = "https://api.openai.com/v1/chat/completions"; break;
                case "anthropic": endpoint = "https://api.anthropic.com/v1/messages"; break;
                case "gemini":
                    if (model.contains("/")) throw new IllegalArgumentException();
                    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent"; break;
                default: throw new IllegalArgumentException();
            }
            String key = secrets.get(provider);
            if (key.isEmpty()) throw new IllegalStateException();
            connection = (HttpsURLConnection) new URL(endpoint).openConnection();
            active = connection;
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(10000);
            connection.setReadTimeout(30000);
            connection.setRequestMethod("POST");
            connection.setRequestProperty("Content-Type", "application/json");
            if (provider.equals("openai")) connection.setRequestProperty("Authorization", "Bearer " + key);
            if (provider.equals("anthropic")) {
                connection.setRequestProperty("x-api-key", key);
                connection.setRequestProperty("anthropic-version", "2023-06-01");
            }
            if (provider.equals("gemini")) connection.setRequestProperty("x-goog-api-key", key);
            byte[] bytes = payload.getBytes(StandardCharsets.UTF_8);
            if (bytes.length > 1024 * 1024) throw new IllegalArgumentException();
            connection.setDoOutput(true);
            connection.setFixedLengthStreamingMode(bytes.length);
            try (java.io.OutputStream output = connection.getOutputStream()) { output.write(bytes); }
            if (connection.getResponseCode() != 200) throw new IllegalStateException();
            long deadline = android.os.SystemClock.elapsedRealtime() + 60000;
            try (InputStream input = connection.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] chunk = new byte[8192]; int count;
                while ((count = input.read(chunk)) != -1) {
                    if (out.size() + count > 4 * 1024 * 1024 || android.os.SystemClock.elapsedRealtime() > deadline)
                        throw new IllegalStateException();
                    out.write(chunk, 0, count);
                }
                return new JSONObject().put("ok", true).put("result",
                    new JSONObject(out.toString(StandardCharsets.UTF_8.name()))).toString();
            }
        } catch (Exception error) {
            return "{\"ok\":false,\"error\":\"Provider unavailable. Check key, model and connection.\"}";
        } finally {
            if (connection != null) connection.disconnect();
            active = null;
        }
    }
}
