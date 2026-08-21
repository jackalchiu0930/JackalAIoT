// 引入 Firebase SDK (Web v9 compat)
importScripts('https://www.gstatic.com/firebasejs/10.9.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.9.0/firebase-messaging-compat.js');

// 初始化 Firebase (請填入您在 Firebase Console 取得的配置)
firebase.initializeApp({
  apiKey: "BOPImwAOEnxu6us4IQmRFa65VLl41NM3e0TYDDTHvisgUAXTdPzqtNlga2swp7zAAGX5jIsym9hVqxk53kgSTCc",
  authDomain: "jackalaiot.firebaseapp.com",
  projectId: "jackalaiot",
  storageBucket: "jackalaiot.appspot.com",
  messagingSenderId: "203370527538",
  appId: "1:203370527538:web:0a08b313693ac0b454752b"
});

const messaging = firebase.messaging();

// 背景接收訊息處理
messaging.onBackgroundMessage((payload) => {
  console.log('[SW] 背景收到 FCM 推播: ', payload);
  const notificationTitle = payload.notification?.title || 'Jackal AIoT 警報';
  const notificationOptions = {
    body: payload.notification?.body || '收到新訊息',
    icon: './Icon_Jackal.png',
    badge: './Icon_Jackal.png',
    data: { url: './alerts.html' }
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});