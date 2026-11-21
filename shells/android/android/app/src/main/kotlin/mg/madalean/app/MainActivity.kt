package mg.madalean.app

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.ContentValues
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.provider.Settings
import androidx.core.content.FileProvider
import java.io.File
import java.security.MessageDigest
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
                    // Tailscale app if installed, else its store page (Play Store, then the web).
                    "openTailscale" -> result.success(openTailscale())
                    // This app's system settings (camera permission refused for good).
                    "openAppSettings" -> {
                        try {
                            startActivity(
                                Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName"))
                                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            )
                            result.success(true)
                        } catch (e: ActivityNotFoundException) {
                            result.success(false)
                        }
                    }
                    // ---- signed self-update (lib/src/update.dart)
                    "abis" -> result.success(Build.SUPPORTED_ABIS.toList())
                    "cacheDir" -> result.success(cacheDir.absolutePath)
                    "apkMatchesInstalled" -> result.success(
                        apkMatchesInstalled(call.argument<String>("path") ?: "")
                    )
                    "canInstall" -> result.success(packageManager.canRequestPackageInstalls())
                    "openInstallSettings" -> {
                        startActivity(
                            Intent(
                                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                Uri.parse("package:$packageName")
                            )
                        )
                        result.success(null)
                    }
                    "installApk" -> {
                        try {
                            installApk(call.argument<String>("path") ?: ""); result.success(null)
                        } catch (e: Exception) {
                            result.error("install", e.message, null)
                        }
                    }
                    else -> result.notImplemented()
                }
            }
    }

    /** "app" (Tailscale opened), "store" (its store page), or "none". */
    private fun openTailscale(): String {
        val pkg = "com.tailscale.ipn"
        packageManager.getLaunchIntentForPackage(pkg)?.let {
            try {
                startActivity(it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); return "app"
            } catch (e: ActivityNotFoundException) { /* fall through */ }
        }
        for (u in listOf("market://details?id=$pkg", "https://play.google.com/store/apps/details?id=$pkg")) {
            try {
                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(u)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                return "store"
            } catch (e: ActivityNotFoundException) { /* next */ }
        }
        return "none"
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

    /** SHA-256 of each signing certificate (current signer set). */
    @Suppress("DEPRECATION")
    private fun certDigests(info: PackageInfo?): Set<String> {
        if (info == null) return emptySet()
        val sigs = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            val si = info.signingInfo ?: return emptySet()
            if (si.hasMultipleSigners()) si.apkContentsSigners else si.signingCertificateHistory
        } else {
            info.signatures
        } ?: return emptySet()
        val md = MessageDigest.getInstance("SHA-256")
        return sigs.map { s -> md.digest(s.toByteArray()).joinToString("") { "%02x".format(it) } }.toSet()
    }

    @Suppress("DEPRECATION")
    private fun apkMatchesInstalled(path: String): Boolean {
        val f = File(path)
        // Only files the updater wrote into our own cache.
        if (!f.isFile || !f.canonicalPath.startsWith(File(cacheDir, "updates").canonicalPath)) return false
        val flags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P)
            PackageManager.GET_SIGNING_CERTIFICATES else PackageManager.GET_SIGNATURES
        val archive = packageManager.getPackageArchiveInfo(f.path, flags) ?: return false
        if (archive.packageName != packageName) return false
        val installed = packageManager.getPackageInfo(packageName, flags)
        val a = certDigests(archive)
        val b = certDigests(installed)
        // The newest signer of the installed app must be in the APK's lineage (equal for us).
        return a.isNotEmpty() && b.isNotEmpty() && a.containsAll(b)
    }

    private fun installApk(path: String) {
        val f = File(path)
        require(f.isFile && f.canonicalPath.startsWith(File(cacheDir, "updates").canonicalPath))
        val uri = FileProvider.getUriForFile(this, "$packageName.updates", f)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        startActivity(intent)
    }
}
