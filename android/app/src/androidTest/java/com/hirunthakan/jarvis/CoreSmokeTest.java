package com.hirunthakan.jarvis;

import android.content.Context;
import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import com.chaquo.python.Python;
import com.chaquo.python.PyObject;
import com.chaquo.python.android.AndroidPlatform;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class CoreSmokeTest {
    @Test public void embeddedCoreStartsWithoutKeysAndAnswersLocally() throws Exception {
        Context context = ApplicationProvider.getApplicationContext();
        if (!Python.isStarted()) Python.start(new AndroidPlatform(context));
        PyObject runtime = Python.getInstance().getModule("mobile.runtime").callAttr("Runtime",
            context.getCacheDir().getAbsolutePath() + "/smoke", new NativeBridge(context), "{}");
        JSONObject response = new JSONObject(runtime.callAttr("chat", "device info").toString());
        assertEquals("LOCAL", response.getString("mode"));
        assertFalse(response.getBoolean("ai_enabled"));
        assertTrue(response.getString("reply").contains("Android"));
        assertEquals(0, response.getJSONArray("pending").length());
        runtime.callAttr("stop");
    }
    @Test public void secretsAreEncryptedAndCanBeDeleted() throws Exception {
        Context context = ApplicationProvider.getApplicationContext();
        SecretStore store = new SecretStore(context);
        try {
            store.put("test-provider", "test-only-not-a-real-key");
            assertEquals("test-only-not-a-real-key", store.get("test-provider"));
            assertFalse(context.getSharedPreferences("provider_secrets", 0)
                .getString("test-provider", "").contains("test-only-not-a-real-key"));
        } finally { store.put("test-provider", ""); }
        assertEquals("", store.get("test-provider"));
    }
}
