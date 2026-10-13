# CampusHub Mobile (Android)

The mobile app is the CampusHub web app (HTML, CSS and JavaScript, no build step) wrapped for
Android with Capacitor. It talks to your existing FastAPI backend, which is not changed.
Every Streamlit screen is ported, with the same fields, validation messages and rules.

```
mobile/
  www/            the app (index.html, app.js, styles.css, sw.js, manifest, icons/)
  assets/         icon source for generating Android icons
  capacitor.config.json
  package.json
```

## What works offline

| Feature | Offline behaviour |
|---|---|
| App screens | Bundled inside the APK, always open |
| Dashboard, Budget, Marketplace, Events | Show the last data loaded (an orange banner says so) |
| Add Expense | Saved on the phone, marked "Pending sync", sent automatically through `/budget/sync-push` when the server is reachable again |
| Income, Marketplace listing, Feedback, Account delete, AI | Need the backend; the app shows the normal "Cannot reach the server" message |
| Study timer | Fully on the phone |
| Sign-in | Stays signed in until the 24 hour token expires (the Streamlit version signed you out on every refresh) |

"Offline" here means no internet. Your phone and the PC running the backend still need to reach
each other (same Wi-Fi or hotspot). The AI runs on the PC through Ollama, not on the phone.

## 1. Try it in a phone browser first (2 minutes)

On the PC, from your CampusHub folder:

```
python run_offline.py --mobile
```

It prints a line like `Mobile app : http://192.168.1.20:8000/app/`. Open that address in
Chrome on your phone (same Wi-Fi). If it does not load, allow Python through the Windows
firewall for private networks.

## 2. Build the Android app in Android Studio

You need Node.js 20 or newer and Android Studio (with an SDK installed). Run once, while online:

```
cd mobile
npm install
npx cap add android
```

Open `android/app/src/main/AndroidManifest.xml` and add `android:usesCleartextTraffic="true"` to the
`<application ...>` tag. This lets the app call your PC over plain `http://` on the local network.

Then:

```
npm run icons      # optional: generates the Android launcher icons from assets/icon-only.png
npx cap sync android
npx cap open android
```

In Android Studio press Run, on an emulator or a USB-connected phone (USB debugging on).
After you change anything in `www/`, run `npx cap sync android` again before pressing Run.

## 3. Connect the app to your PC

Start the backend with `python run_offline.py --mobile`. On the sign-in screen open
**Server settings** and enter:

| Where the app runs | Server address |
|---|---|
| Real phone, same Wi-Fi | `http://<PC address printed by run_offline>:8000` |
| Android emulator | `http://10.0.2.2:8000` |

The address is remembered. Register or sign in as usual.

If you serve your own backend instead of `run_offline.py`, add `http://localhost` to `CORS_ORIGINS`
in `.env` (the Android app's origin).

## Notes and limits

- Fonts: the app uses Inter if you place `Inter-Variable.woff2` in `www/fonts/`, otherwise the phone's
  system font (Roboto). I could not download the font from here.
- Offline expenses are keyed to the signed-in email and survive sign-out; they are sent the next time
  that account is signed in and the server is reachable.
- The Privacy Policy text still says AI runs on Gemini and Groq, as in the original. Edit `PRIVACY_POLICY`
  in `www/app.js` if you ship offline-only.
- Same-origin web use: opening `http://<pc>:8000/app/` in a browser uses the backend on that address
  automatically (no Server settings box).
- Ready for the Play Store later: set a real `appId` in `capacitor.config.json`, create a signing key in
  Android Studio (Build > Generate Signed Bundle), and serve the backend over HTTPS.
