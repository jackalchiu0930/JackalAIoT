// --- 版本配置區 (在此修改版本號，啟動畫面將自動同步) ---
const FE_VERSION = '1.0.7'; // 【更新】版本號更新，觸發PWA更新
const BE_VERSION = '1.0.7';
const AUTHOR = 'AIoT Center | Jackal.Chiu';
const ORG = 'PSA華科事業群';
const CACHE_NAME = 'jackal-v' + FE_VERSION; // 與前端版本連動
const ASSETS = [
  './', 
  './Starting.html', 
  './index.html', 
  './test.html', 
  './alerts.html',
  './class.html',
  './about.html',
  './01_Starting.jpg', 
  './Bg_JackalAIoT.jpg', 
  './Icon_Jackal.png', 
  './manifest.json'
];
// --- 新增：動態獲取後端地址函數 (支持環境變量+原有hostname判斷) ---
const getBackendBaseUrl = () => {
  // Service Worker 中無法直接訪問 window，但可讀取self.location + 環境變量優先
  // Render部署時配置環境變量VITE_BACKEND_URL，本地開發不配置則走原有邏輯
  if (self.location.hostname === 'localhost' || self.location.hostname === '127.0.0.1') {
    return `http://${self.location.hostname}:8000`;
  }
  // 優先使用環境變量，無則用原Render地址（兼容原有部署）
  return self.env?.VITE_BACKEND_URL || 'https://jackalchiu.onrender.com';
};
// --- 新增：清除配置檔標記函數 ---
async function clearConfigFlag() {
  try {
    const backendUrl = getBackendBaseUrl();
    const response = await fetch(`${backendUrl}/config/clear-checked`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      // 確保在install階段也能發送請求
      mode: 'cors'
    });
    
    if (response.ok) {
      console.log('[SW] 配置檔標記已清除（PWA版本更新）');
    } else {
      console.warn('[SW] 清除配置檔標記失敗:', response.status);
    }
  } catch (error) {
    console.error('[SW] 清除配置檔標記請求失敗:', error);
    // 即使失敗也不影響SW安裝
  }
}
self.addEventListener('install', (e) => {
  console.log('[SW] 正在安裝新版本:', FE_VERSION);
  
  // 【核心修改】僅在PWA版本更新時清除標記（而非每次啟動）
  // 判斷是否為新版本安裝（通過cache名稱判斷）
  e.waitUntil(
    caches.keys().then(cacheKeys => {
      // 檢查是否已有當前版本的cache
      const hasCurrentCache = cacheKeys.includes(CACHE_NAME);
      if (!hasCurrentCache) {
        // 新版本首次安裝，才清除配置檔標記
        return clearConfigFlag().then(() => {
          console.log('[SW] 新版本安裝，配置檔初始化完成');
          return self.skipWaiting();
        });
      } else {
        // 已有當前版本cache，跳過清除標記
        console.log('[SW] 當前版本已安裝，跳過配置檔清除');
        return self.skipWaiting();
      }
    }).catch((err) => {
      console.error('[SW] 配置檔初始化失敗，但仍繼續安裝:', err);
      return self.skipWaiting();
    })
  );
});
self.addEventListener('activate', (e) => {
  console.log('[SW] 正在激活新版本:', FE_VERSION);
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.map(k => {
        if (k !== CACHE_NAME) {
          console.log('[SW] 刪除舊緩存:', k);
          return caches.delete(k);
        }
      })
    )).then(() => {
      // 立即接管所有客戶端
      return self.clients.claim();
    })
  );
});
self.addEventListener('push', (event) => {
  let data = { title: 'Jackal AIoT', body: '設備通知' };
  try {
    data = event.data.json();
  } catch (e) {
    data.body = event.data ? event.data.text() : '收到新數據';
  }
  const options = {
    body: data.body,
    icon: './Icon_Jackal.png',
    badge: './Icon_Jackal.png',
    vibrate: [200, 100, 200],
    data: { url: './alerts.html' }
  };
  event.waitUntil(self.registration.showNotification(data.title, options));
});
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});