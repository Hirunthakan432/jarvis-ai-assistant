package com.hirunthakan.jarvis;

import android.app.Activity;
import android.content.Context;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 28)
public class NativeBridgeTest {
    @Test public void onlyWebUrlsWithoutCredentialsAreAccepted() {
        assertTrue(NativeBridge.validUrl("https://example.com/path?q=hello"));
        for (String url : new String[]{"javascript:alert(1)", "file:///etc/passwd", "intent://app",
                "https://user:pass@example.com", "https://example.com/a b", "https:///missing"})
            assertFalse(url, NativeBridge.validUrl(url));
    }
    @Test public void foregroundIsRequiredForEffects() throws Exception {
        NativeBridge bridge = new NativeBridge(RuntimeEnvironment.getApplication());
        assertFalse(new JSONObject(bridge.execute("notify", "{\"text\":\"test\"}")).getBoolean("ok"));
        assertTrue(new JSONObject(bridge.execute("device_info", "{}")).getBoolean("ok"));
    }
    @Test public void deniedCameraFailsWithoutLaunchingPermissionDialog() throws Exception {
        Activity activity = Robolectric.buildActivity(Activity.class).setup().get();
        NativeBridge bridge = new NativeBridge(activity);
        bridge.attach(activity);
        JSONObject result = new JSONObject(bridge.execute("flashlight", "{\"state\":\"on\"}"));
        assertFalse(result.getBoolean("ok"));
        assertTrue(result.getString("error").contains("Permission denied"));
    }
    @Test public void desktopEffectsAreNotNativeActions() throws Exception {
        Activity activity = Robolectric.buildActivity(Activity.class).setup().get();
        NativeBridge bridge = new NativeBridge(activity); bridge.attach(activity);
        assertFalse(new JSONObject(bridge.execute("power_control", "{\"action\":\"restart\"}")).getBoolean("ok"));
        bridge.detach(activity);
        assertFalse(new JSONObject(bridge.execute("set_volume", "{\"percent\":50}")).getBoolean("ok"));
    }
}
