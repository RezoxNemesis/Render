package com.rezox.render.agent;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Device credential ciphertext only; no plaintext preference or repository fallback. */
public final class AgentSecrets {
    private static final String ALIAS="render.agent.device.v1";
    private final SharedPreferences prefs;
    public AgentSecrets(Context c){prefs=c.getSharedPreferences("render_agent",Context.MODE_PRIVATE);}
    private SecretKey key()throws Exception{
        KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
        if(!ks.containsAlias(ALIAS)){
            KeyGenerator gen=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
            gen.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
            gen.generateKey();
        }
        return (SecretKey)ks.getKey(ALIAS,null);
    }
    public synchronized void save(JSONObject credentials)throws Exception{
        Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.ENCRYPT_MODE,key());
        byte[] encrypted=c.doFinal(credentials.toString().getBytes(StandardCharsets.UTF_8));
        if(!prefs.edit().putString("iv",Base64.encodeToString(c.getIV(),Base64.NO_WRAP))
            .putString("secret",Base64.encodeToString(encrypted,Base64.NO_WRAP)).commit())
            throw new IllegalStateException("CREDENTIAL_STORAGE_FAILED");
    }
    public synchronized JSONObject load()throws Exception{
        String encrypted=prefs.getString("secret",null);if(encrypted==null)return null;
        Cipher c=Cipher.getInstance("AES/GCM/NoPadding");
        c.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(prefs.getString("iv",""),Base64.NO_WRAP)));
        return new JSONObject(new String(c.doFinal(Base64.decode(encrypted,Base64.NO_WRAP)),StandardCharsets.UTF_8));
    }
    public void clear(){prefs.edit().remove("secret").remove("iv").putBoolean("enabled",false).commit();}
    public void enabled(boolean value){prefs.edit().putBoolean("enabled",value).commit();}
    public boolean enabled(){return prefs.getBoolean("enabled",false);}
    public void status(String message){prefs.edit().putString("status",message).apply();}
    public String status(){return prefs.getString("status","Not paired. No live ChatGPT connection.");}
}
