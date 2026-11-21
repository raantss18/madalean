package mg.madalean.app

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.ContentValues
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.MediaStore
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val saveRequest = 4711
    private var pendingSave: Pair<ByteArray, MethodChannel.Result>? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "mg.madalean.app/native")
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "deviceName" -> {
                        val maker = Build.MANUFACTURER.replaceFirstChar { it.uppercase() }
                        val model = Build.MODEL
                        result.success(if (model.startsWith(maker, ignoreCase = true)) model else "$maker $model")
                    }
                    "appVersion" -> result.success(
                        packageManager.getPackageInfo(packageName, 0).versionName ?: ""
                    )
                    "saveDownload" -> {
                        val name = call.argument<String>("name") ?: "madalean-export"
                        val mime = call.argument<String>("mime") ?: "application/octet-stream"
                        val bytes = call.argument<ByteArray>("bytes") ?: ByteArray(0)
                        saveDownload(name, mime, bytes, result)
                    }
                    "openUri" -> {
                        val uri = Uri.parse(call.argument<String>("uri"))
                        val view = Intent(Intent.ACTION_VIEW).apply {
                            setDataAndType(uri, call.argument<String>("mime"))
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        }
                        try {
                            startActivity(view); result.success(true)
                        } catch (e: ActivityNotFoundException) {
                            result.success(false)
                        }
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private fun saveDownload(name: String, mime: String, bytes: ByteArray, result: MethodChannel.Result) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // Android 10+: public Downloads through MediaStore, no permission needed.
            try {
                val values = ContentValues().apply {
                    put(MediaStore.Downloads.DISPLAY_NAME, name)
                    put(MediaStore.Downloads.MIME_TYPE, mime)
                    put(MediaStore.Downloads.IS_PENDING, 1)
                }
                val resolver = contentResolver
                val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                    ?: return result.error("save", "insert failed", null)
                resolver.openOutputStream(uri)?.use { it.write(bytes) }
                values.clear()
                values.put(MediaStore.Downloads.IS_PENDING, 0)
                resolver.update(uri, values, null, null)
                result.success(uri.toString())
            } catch (e: Exception) {
                result.error("save", e.message, null)
            }
        } else {
            // Android 8–9: let the user pick the place (Storage Access Framework), no permission.
            pendingSave = Pair(bytes, result)
            val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = mime
                putExtra(Intent.EXTRA_TITLE, name)
            }
            @Suppress("DEPRECATION")
            startActivityForResult(intent, saveRequest)
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (requestCode == saveRequest) {
            val (bytes, result) = pendingSave ?: return
            pendingSave = null
            val uri = data?.data
            if (resultCode != Activity.RESULT_OK || uri == null) {
                result.success(null); return
            }
            try {
                contentResolver.openOutputStream(uri)?.use { it.write(bytes) }
                result.success(uri.toString())
            } catch (e: Exception) {
                result.error("save", e.message, null)
            }
            return
        }
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
    }
}
