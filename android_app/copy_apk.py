import os
import shutil

source_apk = r"D:\MyConfiguration\admin\AndroidStudioProjects\mi-tv-launcher\tv-launcher-app\app\build\outputs\apk\debug\app-debug.apk"
target_dir = r"D:\MyConfiguration\admin\AndroidStudioProjects\mi-tv-launcher\backend\static\ota"
target_apk = os.path.join(target_dir, "app-debug.apk")

if not os.path.exists(target_dir):
    os.makedirs(target_dir)

shutil.copy2(source_apk, target_apk)
print(f"APK copied to {target_apk}")
