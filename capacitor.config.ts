import type { CapacitorConfig } from "@capacitor/cli";

const mode = process.env.FARMSOURCE_APP_MODE === "driver" ? "driver" : "shop";
const baseServerUrl = process.env.FARMSOURCE_MOBILE_SERVER_URL || "http://10.0.2.2:8001";
const appSettings = {
  shop: {
    appId: "com.farmsource.shop",
    appName: "Farmsource Shop",
    path: "/customer/catalog",
  },
  driver: {
    appId: "com.farmsource.driver",
    appName: "Farmsource Driver",
    path: "/driver",
  },
}[mode];

const serverUrl = new URL(appSettings.path, baseServerUrl).toString();

const config: CapacitorConfig = {
  appId: appSettings.appId,
  appName: appSettings.appName,
  webDir: "app/static",
  server: {
    url: serverUrl,
    cleartext: serverUrl.startsWith("http://"),
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 1200,
      backgroundColor: "#f7f5ef",
      showSpinner: false,
    },
  },
};

export default config;
