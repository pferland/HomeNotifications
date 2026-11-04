/**
 * HomeNotifications Modern Management UI Frontend Application
 */

document.addEventListener('DOMContentLoaded', () => {
  // App State
  let currentTab = 'dashboard';
  let refreshTimer = null;
  let allDevices = [];
  let allDiscovery = [];
  let allServices = [];
  let allFeatures = {};

  // Table Sorting State
  let devicesSort = { column: 'name', asc: true };
  let discoverySort = { column: 'ip', asc: true };
  let servicesSort = { column: 'service_name', asc: true };

  // Elements
  const navItems = document.querySelectorAll('.sidebar-nav .nav-item');
  const tabPanels = document.querySelectorAll('.tab-panel');
  const viewTitle = document.getElementById('view-title');
  const viewBreadcrumb = document.getElementById('view-breadcrumb');
  const themeToggle = document.getElementById('theme-toggle');
  const autoRefreshSelect = document.getElementById('auto-refresh-select');
  const toast = document.getElementById('toast');
  let toastTimer = null;

  function showToast(message, duration = 3500) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove('show');
    }, duration);
  }

  // Modals & Forms
  const deviceModal = document.getElementById('device-modal');
  const deviceForm = document.getElementById('device-form');
  const btnOpenAddDevice = document.getElementById('btn-open-add-device');
  const btnCloseModal = document.getElementById('btn-close-modal');
  const btnCancelModal = document.getElementById('btn-cancel-modal');

  // Service Modal Elements
  const serviceModal = document.getElementById('service-modal');
  const serviceForm = document.getElementById('service-form');
  const serviceModalTitle = document.getElementById('service-modal-title');
  const btnOpenAddService = document.getElementById('btn-open-add-service');
  const btnCloseServiceModal = document.getElementById('btn-close-service-modal');
  const btnCancelServiceModal = document.getElementById('btn-cancel-service-modal');
  const btnTestServiceProbe = document.getElementById('btn-test-service-probe');
  const serviceProbeResult = document.getElementById('service-probe-result');
  const formSrvDevice = document.getElementById('form-srv-device');
  const formSrvDiscovered = document.getElementById('form-srv-discovered');
  const formSrvDiscoveryStatus = document.getElementById('form-srv-discovery-status');
  const btnRefreshDiscoveredServices = document.getElementById('btn-refresh-discovered-services');
  const formSrvName = document.getElementById('form-srv-name');
  const formSrvOriginalName = document.getElementById('form-srv-original-name');
  const formSrvType = document.getElementById('form-srv-type');
  const formSrvPort = document.getElementById('form-srv-port');
  const formSrvPath = document.getElementById('form-srv-path');
  const formSrvStatus = document.getElementById('form-srv-status');
  const formSrvTimeout = document.getElementById('form-srv-timeout');
  const formSrvHttpOptions = document.getElementById('form-srv-http-options');
  const formSrvHostname = document.getElementById('form-srv-hostname');
  const formSrvCheckSsl = document.getElementById('form-srv-check-ssl');

  // Quick Action Buttons
  const btnTriggerScan = document.getElementById('btn-trigger-scan');
  const btnRunDiscoveryScan = document.getElementById('btn-run-discovery-scan');
  const btnCheckDevices = document.getElementById('btn-check-devices');
  const btnFlushBatch = document.getElementById('btn-flush-batch');
  const btnSendTestTg = document.getElementById('btn-send-test-tg');
  const btnSaveFeatures = document.getElementById('btn-save-features');
  const btnReloadFeatures = document.getElementById('btn-reload-features');

  // Feature Configuration Modal Elements
  const featureModal = document.getElementById('feature-modal');
  const featureForm = document.getElementById('feature-form');
  const featureModalIcon = document.getElementById('feature-modal-icon');
  const featureModalTitle = document.getElementById('feature-modal-title');
  const featureModalDesc = document.getElementById('feature-modal-desc');
  const btnCloseFeatureModal = document.getElementById('btn-close-feature-modal');
  const btnCancelFeatureModal = document.getElementById('btn-cancel-feature-modal');
  const btnSaveFeatureModal = document.getElementById('btn-save-feature-modal');
  const formFeatName = document.getElementById('form-feat-name');
  const formFeatEnabled = document.getElementById('form-feat-enabled');
  const formFeatEnabledLabel = document.getElementById('form-feat-enabled-label');
  const formFeatInterval = document.getElementById('form-feat-interval');
  const formFeatMode = document.getElementById('form-feat-mode');
  const formFeatBatchGroup = document.getElementById('form-feat-batch-group');
  const formFeatBatchInterval = document.getElementById('form-feat-batch-interval');
  const formFeatSuboptionsCount = document.getElementById('form-feat-suboptions-count');
  const featureModalSuboptions = document.getElementById('feature-modal-suboptions');

  // Speedtest Modal Elements
  const speedtestModal = document.getElementById('speedtest-modal');
  const btnCloseSpeedtestModal = document.getElementById('btn-close-speedtest-modal');
  const btnCloseSpeedtestFooter = document.getElementById('btn-close-speedtest-footer');
  const btnRunSpeedtestModal = document.getElementById('btn-run-speedtest-modal');
  const speedtestStatusHeadline = document.getElementById('speedtest-status-headline');
  const speedtestStatusSub = document.getElementById('speedtest-status-sub');
  const speedtestComparisonContainer = document.getElementById('speedtest-comparison-container');
  const speedtestTargetsTbody = document.getElementById('speedtest-targets-tbody');
  const speedtestTargetsCount = document.getElementById('speedtest-targets-count');
  const speedtestConfigToggle = document.getElementById('speedtest-config-toggle');
  const speedtestConfigToggleIcon = document.getElementById('speedtest-config-toggle-icon');
  const speedtestSettingsForm = document.getElementById('speedtest-settings-form');
  const btnDiscoverSpeedtestServers = document.getElementById('btn-discover-speedtest-servers');
  const stCfgServersSelect = document.getElementById('st-cfg-servers-select');
  const stServersDropdownContainer = document.getElementById('st-servers-dropdown-container');

  // Process Breakdown Modal Elements
  const processModal = document.getElementById('process-modal');
  const btnCloseProcessModal = document.getElementById('btn-close-process-modal');
  const btnCloseProcessModalBottom = document.getElementById('btn-close-process-modal-bottom');
  const processModalTitle = document.getElementById('process-modal-title');
  const processModalSubtitle = document.getElementById('process-modal-subtitle');
  const processModalCpuLoad = document.getElementById('process-modal-cpu-load');
  const processModalMemStats = document.getElementById('process-modal-mem-stats');
  const btnRefreshProcessesLive = document.getElementById('btn-refresh-processes-live');
  const processModalRefreshIcon = document.getElementById('process-modal-refresh-icon');
  const btnTabProcsCpu = document.getElementById('btn-tab-procs-cpu');
  const btnTabProcsMem = document.getElementById('btn-tab-procs-mem');
  const inputFilterProcesses = document.getElementById('input-filter-processes');
  const tbodyModalProcesses = document.getElementById('tbody-modal-processes');
  const btnRefreshResources = document.getElementById('btn-refresh-resources');

  let cachedResources = [];
  let cardProcessTabs = {};
  let modalProcessState = { deviceId: null, tab: 'cpu', filter: '' };

  // Search & Filter Inputs
  const devicesSearchInput = document.getElementById('devices-search-input');
  const discoverySearchInput = document.getElementById('discovery-search-input');
  const servicesSearchInput = document.getElementById('services-search-input');
  const featuresSearchInput = document.getElementById('features-search-input');
  const featuresFilterChips = document.getElementById('features-filter-chips');
  const featuresSummaryStats = document.getElementById('features-summary-stats');

  // Feature Filter State
  let currentFeatureFilter = 'all';
  let featureSearchQuery = '';

  // --- HTML Entity Escaper ---
  function escapeHtml(str) {
    if (str === undefined || str === null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // --- Feature Categories & Definitions ---
  const featureCategories = {
    network: {
      name: 'Network & Infrastructure',
      icon: '🌐',
      desc: 'Connectivity, port health probes, ARP sweeps, switch telemetry, and WAN quality'
    },
    security: {
      name: 'Security & Access Watchdogs',
      icon: '🛡️',
      desc: 'SSH authentication audits, HTTPS certificates, and webhook triggers'
    },
    home: {
      name: 'Household & Family',
      icon: '🏠',
      desc: 'Resident Wi-Fi presence tracking and nighttime quiet-hours activity'
    },
    power: {
      name: 'Power & Telemetry Sensors',
      icon: '⚡',
      desc: 'UPS battery outage detection and ambient lux levels'
    },
    advisories: {
      name: 'Community & Advisories',
      icon: '🚩',
      desc: 'Official presidential and state half-staff flag status'
    }
  };

  const featureMeta = {
    presence: {
      title: 'Resident Wi-Fi Presence',
      icon: '👋',
      category: 'home',
      desc: 'Tracks household members via Wi-Fi and alerts on arrival or departure.',
      suboptions: [
        { key: 'alert_arrival', label: 'Alert on Arrival', type: 'checkbox', default: true },
        { key: 'alert_departure', label: 'Alert on Departure', type: 'checkbox', default: true },
        { key: 'away_threshold_seconds', label: 'Away Threshold (sec)', type: 'number', default: 900 },
        { key: 'members', label: 'Residents (Name:MAC/IP)', type: 'text', default: 'Paul:dc:a6:32:5c:27:2a' }
      ]
    },
    ssl_cert: {
      title: 'SSL / TLS Certificate Expiry',
      icon: '🔒',
      category: 'security',
      desc: 'Probes HTTPS endpoints and warns before SSL certificates expire.',
      suboptions: [
        { key: 'alert_expiring_soon', label: 'Alert Expiring Soon', type: 'checkbox', default: true },
        { key: 'alert_expired', label: 'Alert on Expired', type: 'checkbox', default: true },
        { key: 'warning_days', label: 'Warning Threshold (days)', type: 'number', default: 14 },
        { key: 'critical_days', label: 'Critical Threshold (days)', type: 'number', default: 3 },
        { key: 'custom_targets', label: 'Custom Targets (host:port)', type: 'text', default: '' }
      ]
    },
    webhooks: {
      title: 'Smart Home Webhook Hub',
      icon: '🔌',
      category: 'security',
      desc: 'Secured endpoint (/api/webhook/notify) for Home Assistant, 3D printers, and NVRs.',
      suboptions: [
        { key: 'allow_unauthenticated', label: 'Allow Without Token', type: 'checkbox', default: false },
        { key: 'api_key', label: 'Secret Webhook API Key', type: 'text', default: 'homenotify-secret-key' }
      ]
    },
    speedtest: {
      title: 'Internet Speed & WAN Quality',
      icon: '⚡',
      category: 'network',
      desc: 'Measures download/upload throughput and multi-target latency against speedtest servers and custom IPs.',
      suboptions: [
        { key: 'provider', label: 'Speedtest Engine / Provider (ookla, cloudflare)', type: 'text', default: 'ookla' },
        { key: 'server_id', label: 'Ookla Server ID (Blank = Auto-Closest)', type: 'text', default: '' },
        { key: 'server_location', label: 'Preferred Server Name / Location', type: 'text', default: '' },
        { key: 'latency_targets', label: 'Latency Test Targets (comma-separated IPs/hostnames)', type: 'text', default: '1.1.1.1, 8.8.8.8, 9.9.9.9' },
        { key: 'alert_on_degraded', label: 'Alert on Degradation', type: 'checkbox', default: true },
        { key: 'min_download_mbps', label: 'Min Download (Mbps)', type: 'number', default: 25.0 },
        { key: 'min_upload_mbps', label: 'Min Upload (Mbps)', type: 'number', default: 5.0 },
        { key: 'max_latency_ms', label: 'Max Latency (ms)', type: 'number', default: 120.0 }
      ]
    },
    cisco_snmp: {
      title: 'Cisco Switch & SNMP Monitor',
      icon: '🔀',
      category: 'network',
      desc: 'Polls managed switches for port operational status and link drops.',
      suboptions: [
        { key: 'alert_link_down', label: 'Alert on Port Down', type: 'checkbox', default: true },
        { key: 'alert_port_saturation', label: 'Alert on High Traffic', type: 'checkbox', default: true },
        { key: 'saturation_threshold_mbps', label: 'Saturation Limit (Mbps)', type: 'number', default: 100.0 },
        { key: 'device_id', label: 'Target Switch Device ID', type: 'text', default: 'core-switch' },
        { key: 'monitored_ports', label: 'Monitored Switch Ports', type: 'text', default: 'all' }
      ]
    },
    ups_monitor: {
      title: 'UPS Battery & Power Outage',
      icon: '🔋',
      category: 'power',
      desc: 'Detects mains power outages and critical battery levels via NUT or circuit probe.',
      suboptions: [
        { key: 'alert_on_battery', label: 'Alert on Power Loss', type: 'checkbox', default: true },
        { key: 'alert_low_battery', label: 'Alert on Low Battery', type: 'checkbox', default: true },
        { key: 'alert_power_restored', label: 'Alert on Power Restored', type: 'checkbox', default: true },
        { key: 'low_battery_percent', label: 'Low Battery % Trigger', type: 'number', default: 25 },
        { key: 'ups_type', label: 'Type (probe, nut, apcupsd)', type: 'text', default: 'probe' },
        { key: 'probe_host', label: 'Mains Circuit Probe IP', type: 'text', default: '192.168.1.1' },
        { key: 'host', label: 'NUT / Daemon Host', type: 'text', default: '127.0.0.1' },
        { key: 'port', label: 'NUT / Daemon Port', type: 'number', default: 3493 }
      ]
    },
    night_owl: {
      title: 'Night Owl Quiet Hours Activity',
      icon: '🌙',
      category: 'home',
      desc: 'Alerts if entertainment or kids devices are actively used during sleep hours.',
      suboptions: [
        { key: 'alert_active', label: 'Alert on Night Usage', type: 'checkbox', default: true },
        { key: 'quiet_start', label: 'Quiet Start (HH:MM)', type: 'text', default: '01:00' },
        { key: 'quiet_end', label: 'Quiet End (HH:MM)', type: 'text', default: '05:30' },
        { key: 'monitored_tags', label: 'Monitored Device Tags', type: 'text', default: 'kids,console,entertainment' },
        { key: 'monitored_macs', label: 'Monitored MAC Addresses', type: 'text', default: '' },
        { key: 'cooldown_minutes', label: 'Alert Cooldown (min)', type: 'number', default: 60 }
      ]
    },
    network_discovery: {
      title: 'Network Discovery & ARP Sweep',
      icon: '🌐',
      category: 'network',
      desc: 'Discovers active devices and alerts when unknown hosts connect.',
      suboptions: [
        { key: 'alert_new_device', label: 'Alert on New Device', type: 'checkbox', default: true },
        { key: 'alert_device_offline', label: 'Alert on Device Offline', type: 'checkbox', default: false },
        { key: 'offline_threshold_seconds', label: 'Offline Threshold (sec)', type: 'number', default: 1800 },
        { key: 'subnets', label: 'Target Subnets', type: 'text', default: 'auto' }
      ]
    },
    device_monitor: {
      title: 'Device & Services Health Monitor',
      icon: '🖥️',
      category: 'network',
      desc: 'Pings hosts and checks ports, services, and SSH metrics.',
      suboptions: [
        { key: 'alert_on_down', label: 'Alert on Device DOWN', type: 'checkbox', default: true },
        { key: 'alert_on_recovery', label: 'Alert on Recovery', type: 'checkbox', default: true },
        { key: 'cooldown_seconds', label: 'Alert Cooldown (sec)', type: 'number', default: 3600 }
      ]
    },
    access_logs: {
      title: 'SSH Access Log Watchdog',
      icon: '🛡️',
      category: 'security',
      desc: 'Audits /var/log/auth.log for failed logins and brute-force attempts.',
      suboptions: [
        { key: 'failed_login_threshold', label: 'Failed Attempts Trigger', type: 'number', default: 3 }
      ]
    },
    external_ip: {
      title: 'External Public IP Monitor',
      icon: '🌍',
      category: 'network',
      desc: 'Monitors public IPv4 address and alerts when WAN IP changes.',
      suboptions: []
    },
    flag_status: {
      title: 'Flag Half-Staff Monitor',
      icon: '🚩',
      category: 'advisories',
      desc: 'Monitors customizable Wikipedia articles and incident rules to alert when flags should fly at half-staff.',
      suboptions: [
        { key: 'duration_days', label: 'Half-Staff Alert Duration (Days)', type: 'number', default: 4 },
        { key: 'min_deaths', label: 'Minimum Fatalities Threshold', type: 'number', default: 1 },
        { key: 'min_casualties', label: 'Minimum Total Casualties Threshold', type: 'number', default: 1 },
        { key: 'state_filter', label: 'State / Location Filter (e.g. FL, TX or blank for Nationwide)', type: 'text', default: '' }
      ]
    },
    photolevel: {
      title: 'Ambient Light Level (Photo)',
      icon: '☀️',
      category: 'power',
      desc: 'Reads ambient lux levels from I2C ADC hardware.',
      suboptions: []
    }
  };

  // --- View & Route Hierarchy Map ---
  const routeHierarchy = {
    dashboard: {
      title: 'Dashboard Overview',
      section: 'Monitoring',
      trail: [
        { label: 'Home', hash: '#dashboard' },
        { label: 'Dashboard' }
      ]
    },
    devices: {
      title: 'Monitored Devices Inventory',
      section: 'Monitoring',
      trail: [
        { label: 'Home', hash: '#dashboard' },
        { label: 'Monitoring', hash: '#devices' },
        { label: 'Monitored Devices' }
      ]
    },
    discovery: {
      title: 'Network Discovery & ARP Cache',
      section: 'Monitoring',
      trail: [
        { label: 'Home', hash: '#dashboard' },
        { label: 'Monitoring', hash: '#discovery' },
        { label: 'Network Discovery' }
      ]
    },
    services: {
      title: 'Services & Port Health',
      section: 'Monitoring',
      trail: [
        { label: 'Home', hash: '#dashboard' },
        { label: 'Monitoring', hash: '#services' },
        { label: 'Services & Ports' }
      ]
    },
    resources: {
      title: 'System Resources & Telemetry',
      section: 'Monitoring',
      trail: [
        { label: 'Home', hash: '#dashboard' },
        { label: 'Monitoring', hash: '#resources' },
        { label: 'System Resources' }
      ]
    },
    features: {
      title: 'Feature Schedules & Notification Modes',
      section: 'Configuration',
      trail: [
        { label: 'Home', hash: '#dashboard' },
        { label: 'Configuration', hash: '#features' },
        { label: 'Features & Alerts' }
      ]
    }
  };

  const viewTitles = routeHierarchy;

  // --- Breadcrumbs Trail Rendering ---
  function updateBreadcrumbs(tabId, subId = null) {
    if (!viewBreadcrumb) return;
    const info = routeHierarchy[tabId] || routeHierarchy.dashboard;
    let trail = [...info.trail];

    if (tabId === 'features' && subId) {
      const featMeta = featureMeta[subId];
      const featLabel = featMeta?.title || subId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
      trail = [
        { label: 'Home', hash: '#dashboard' },
        { label: 'Configuration', hash: '#features' },
        { label: 'Features & Alerts', hash: '#features' },
        { label: featLabel }
      ];
    } else if (tabId === 'devices' && subId) {
      let devLabel = 'Device Details';
      if (subId === 'add') {
        devLabel = 'Add Device';
      } else if (subId.startsWith('edit/')) {
        const id = decodeURIComponent(subId.replace('edit/', ''));
        const dev = allDevices.find(d => d.id === id);
        devLabel = dev ? `Edit ${dev.name}` : `Edit Device (${id})`;
      }
      trail = [
        { label: 'Home', hash: '#dashboard' },
        { label: 'Monitoring', hash: '#devices' },
        { label: 'Monitored Devices', hash: '#devices' },
        { label: devLabel }
      ];
    } else if (tabId === 'services' && subId) {
      let srvLabel = 'Service Details';
      if (subId === 'add') {
        srvLabel = 'Add Service';
      } else if (subId.startsWith('add/')) {
        const targetDevId = decodeURIComponent(subId.replace('add/', ''));
        const targetDev = allDevices.find(d => d.id === targetDevId);
        srvLabel = targetDev ? `Add Service (${targetDev.name})` : `Add Service (${targetDevId})`;
      } else if (subId.startsWith('edit/')) {
        const srvName = decodeURIComponent(subId.replace('edit/', ''));
        srvLabel = `Edit ${srvName}`;
      }
      trail = [
        { label: 'Home', hash: '#dashboard' },
        { label: 'Monitoring', hash: '#services' },
        { label: 'Services & Ports', hash: '#services' },
        { label: srvLabel }
      ];
    }

    const html = trail.map((crumb, idx) => {
      const isLast = idx === trail.length - 1;
      if (isLast || !crumb.hash) {
        return `<span class="breadcrumb-item breadcrumb-current">${escapeHtml(crumb.label)}</span>`;
      }
      return `<a href="${escapeHtml(crumb.hash)}" class="breadcrumb-item breadcrumb-link">${escapeHtml(crumb.label)}</a>`;
    }).join('<span class="breadcrumb-separator">/</span>');

    viewBreadcrumb.innerHTML = html;
  }

  // --- Route Parser & Navigation ---
  function parseRoute(hash) {
    const raw = (hash || window.location.hash || '').replace(/^#\/?/, '').trim();
    if (!raw) return { tab: 'dashboard', sub: null };

    const [pathPart, queryPart] = raw.split('?');
    const segments = pathPart.split('/').map(s => s.trim()).filter(Boolean);
    const tabCandidate = (segments[0] || 'dashboard').toLowerCase();
    const tab = routeHierarchy[tabCandidate] ? tabCandidate : 'dashboard';
    let sub = segments.slice(1).join('/') || null;

    if (queryPart && !sub) {
      const params = new URLSearchParams(queryPart);
      sub = params.get('feature') || params.get('modal') || params.get('sub') || params.get('device') || null;
    }

    return { tab, sub };
  }

  function navigateTo(tabId, sub = null, updateHash = true) {
    if (!routeHierarchy[tabId]) tabId = 'dashboard';
    const targetHash = sub ? `#${tabId}/${sub}` : `#${tabId}`;

    try {
      localStorage.setItem('homenotify_last_route', targetHash);
    } catch (e) {
      console.debug('Failed saving last route to localStorage', e);
    }

    if (updateHash && window.location.hash !== targetHash) {
      window.location.hash = targetHash;
      return;
    }

    switchTab(tabId, sub);
  }

  // --- Tab & Subview Switcher ---
  function switchTab(tabId, sub = null) {
    if (!routeHierarchy[tabId]) tabId = 'dashboard';
    currentTab = tabId;

    try {
      localStorage.setItem('homenotify_last_route', sub ? `#${tabId}/${sub}` : `#${tabId}`);
    } catch (e) {
      console.debug('Failed saving last route to localStorage', e);
    }

    navItems.forEach(item => {
      item.classList.toggle('active', item.getAttribute('data-tab') === tabId);
    });

    tabPanels.forEach(panel => {
      panel.classList.toggle('active', panel.id === `panel-${tabId}`);
    });

    const routeInfo = routeHierarchy[tabId] || routeHierarchy.dashboard;
    if (tabId === 'features' && sub) {
      const featMeta = featureMeta[sub];
      const featTitle = featMeta?.title || sub.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
      viewTitle.textContent = `${featTitle} Configuration`;
    } else if (tabId === 'devices' && sub) {
      if (sub === 'add') {
        viewTitle.textContent = 'Add Monitored Device';
      } else if (sub.startsWith('edit/')) {
        const id = decodeURIComponent(sub.replace('edit/', ''));
        const dev = allDevices.find(d => d.id === id);
        viewTitle.textContent = dev ? `Edit Monitored Device: ${dev.name}` : `Edit Device (${id})`;
      }
    } else if (tabId === 'services' && sub) {
      if (sub === 'add') {
        viewTitle.textContent = 'Add Monitored Service';
      } else if (sub.startsWith('add/')) {
        const targetDevId = decodeURIComponent(sub.replace('add/', ''));
        const dev = allDevices.find(d => d.id === targetDevId);
        viewTitle.textContent = dev ? `Add Monitored Service: ${dev.name}` : `Add Monitored Service (${targetDevId})`;
      } else if (sub.startsWith('edit/')) {
        const srvName = decodeURIComponent(sub.replace('edit/', ''));
        viewTitle.textContent = `Edit Monitored Service: ${srvName}`;
      }
    } else {
      viewTitle.textContent = routeInfo.title;
    }

    updateBreadcrumbs(tabId, sub);

    // Refresh tab specific data immediately
    if (tabId === 'devices') loadDevices();
    if (tabId === 'discovery') loadDiscovery();
    if (tabId === 'services') loadServices();
    if (tabId === 'resources') loadResources();
    if (tabId === 'features') {
      loadFeatures();
      loadTelegramConfig();
    }

    // Modal state synchronization
    if (tabId === 'speedtest' || (tabId === 'features' && sub === 'speedtest')) {
      openSpeedtestModal(false);
    } else {
      if (speedtestModal && speedtestModal.classList.contains('open')) {
        speedtestModal.classList.remove('open');
      }
    }

    if (tabId === 'features' && sub && sub !== 'speedtest') {
      if (allFeatures && allFeatures[sub]) {
        openFeatureModal(sub, false);
      } else {
        loadFeatures().then(() => {
          if (allFeatures && allFeatures[sub]) {
            openFeatureModal(sub, false);
          }
        });
      }
    } else if (tabId === 'features' && !sub) {
      if (featureModal && featureModal.classList.contains('open')) {
        featureModal.classList.remove('open');
      }
    }

    if (tabId === 'devices' && sub) {
      if (sub === 'add') {
        openDeviceModal(null, false);
      } else if (sub.startsWith('edit/')) {
        const devId = decodeURIComponent(sub.replace('edit/', ''));
        if (allDevices && allDevices.length > 0) {
          const dev = allDevices.find(d => d.id === devId);
          if (dev) {
            openDeviceModal(dev, false);
            updateBreadcrumbs(tabId, sub);
          }
        } else {
          loadDevices().then(() => {
            const dev = allDevices.find(d => d.id === devId);
            if (dev) {
              openDeviceModal(dev, false);
              updateBreadcrumbs(tabId, sub);
            }
          });
        }
      }
    } else if (tabId === 'devices' && !sub) {
      if (deviceModal && deviceModal.classList.contains('open')) {
        deviceModal.classList.remove('open');
      }
    }

    if (tabId === 'services' && sub) {
      if (sub === 'add' || sub.startsWith('add/')) {
        const targetDevId = sub.startsWith('add/') ? decodeURIComponent(sub.replace('add/', '')) : '';
        const openAdd = () => {
          const pickedDevId = targetDevId || (allDevices.length ? allDevices[0].id : '');
          openServiceModalForDevice(pickedDevId, null, false);
          updateBreadcrumbs(tabId, sub);
        };
        if (!allDevices || allDevices.length === 0) {
          loadDevices().then(openAdd);
        } else {
          openAdd();
        }
      } else if (sub.startsWith('edit/')) {
        const srvName = decodeURIComponent(sub.replace('edit/', ''));
        const openEdit = () => {
          const srv = allServices.find(s => s.service_name === srvName);
          if (srv) {
            openServiceModalForDevice(srv.device_id, srv, false);
            updateBreadcrumbs(tabId, sub);
          }
        };
        const promises = [];
        if (!allServices || allServices.length === 0) promises.push(loadServices());
        if (!allDevices || allDevices.length === 0) promises.push(loadDevices());
        if (promises.length > 0) {
          Promise.all(promises).then(openEdit);
        } else {
          openEdit();
        }
      }
    } else if (tabId === 'services' && !sub) {
      if (serviceModal && serviceModal.classList.contains('open')) {
        serviceModal.classList.remove('open');
      }
    }

    // Ensure modals for inactive tabs are closed
    if (tabId !== 'features' && featureModal && featureModal.classList.contains('open')) {
      featureModal.classList.remove('open');
    }
    if (tabId !== 'devices' && deviceModal && deviceModal.classList.contains('open')) {
      deviceModal.classList.remove('open');
    }
    if (tabId !== 'services' && serviceModal && serviceModal.classList.contains('open')) {
      serviceModal.classList.remove('open');
    }
    if (tabId !== 'resources' && processModal && processModal.classList.contains('open')) {
      closeProcessModal();
    }
  }

  // Intercept click on data-tab and breadcrumb links
  document.addEventListener('click', (e) => {
    const tabEl = e.target.closest('[data-tab]');
    if (tabEl) {
      e.preventDefault();
      const tabId = tabEl.getAttribute('data-tab');
      if (tabId) {
        navigateTo(tabId);
        return;
      }
    }

    const crumbLink = e.target.closest('.breadcrumb-link');
    if (crumbLink) {
      e.preventDefault();
      const targetHash = crumbLink.getAttribute('href');
      if (targetHash) {
        const { tab, sub } = parseRoute(targetHash);
        navigateTo(tab, sub);
        return;
      }
    }
  });

  window.addEventListener('hashchange', () => {
    const { tab, sub } = parseRoute(window.location.hash);
    switchTab(tab, sub);
  });

  // --- API Loaders ---
  let latestStatusData = null;
  let dashFeatureFilter = 'all';

  async function loadStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      if (!data.success) return;
      latestStatusData = data;
      renderDashboardFeatureTiles();

      // KPI Elements
      document.getElementById('kpi-devices-total').textContent = data.devices.total;
      document.getElementById('kpi-devices-up').textContent = `${data.devices.up} UP`;
      document.getElementById('kpi-devices-down').textContent = `${data.devices.down} DOWN`;
      document.getElementById('kpi-hosts-total').textContent = data.network_discovery.total_known;
      document.getElementById('kpi-hosts-online').textContent = `${data.network_discovery.online_count} online in ARP cache`;
      document.getElementById('kpi-external-ip').textContent = data.external_ip;
      document.getElementById('kpi-queued-alerts').textContent = data.queued_notifications;

      // Nav badges
      document.getElementById('nav-badge-devices').textContent = data.devices.total;
      document.getElementById('nav-badge-discovery').textContent = data.network_discovery.total_known;

      // Flag status
      const flagBox = document.getElementById('flag-text-box');
      const flagBadge = document.getElementById('flag-status-badge');
      const flagBanner = document.getElementById('flag-visual-banner');
      const flagTbody = document.getElementById('flag-recent-tbody');
      const details = data.flag_status_details || {};
      const statusText = data.flag_status || 'Not Checked';
      if (flagBox) flagBox.textContent = statusText;

      const isLower = (details.status_type === 'LOWER') || statusText.includes('Lower Flag');
      const isRaise = (details.status_type === 'RAISE') || statusText.includes('Raise Flag');

      if (flagBadge) {
        if (isLower) {
          flagBadge.textContent = '🔻 Lower Flag (Half-Staff)';
          flagBadge.className = 'badge badge-danger';
        } else if (isRaise) {
          flagBadge.textContent = '🏳️ Full-Staff (Normal)';
          flagBadge.className = 'badge badge-success';
        } else {
          flagBadge.textContent = 'Normal';
          flagBadge.className = 'badge badge-muted';
        }
      }

      if (flagBanner) {
        flagBanner.style.display = 'block';
        if (isLower && details.active_incident) {
          const inc = details.active_incident;
          flagBanner.className = 'flag-banner-lower';
          flagBanner.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
              <strong style="color: var(--danger); font-size: 13.5px; display: flex; align-items: center; gap: 6px;">
                <span>🚩</span> HALF-STAFF ALERT: LOWER FLAGS
              </strong>
              <span class="badge badge-danger">${inc.days_ago === 0 ? 'Today' : inc.days_ago + ' days ago'}</span>
            </div>
            <div style="font-size: 12.5px; margin-bottom: 4px;">
              <strong>📍 Location:</strong> ${escapeHtml(inc.location)} &bull; 
              <strong>📅 Date:</strong> ${escapeHtml(inc.date)}
            </div>
            <div style="font-size: 12px; margin-bottom: 6px;">
              <strong>💀 Casualties:</strong> ${inc.dead} Dead, ${inc.injured} Injured (${inc.total} Total)
            </div>
            ${inc.desc ? `<div style="font-size: 11.5px; color: var(--text-muted); font-style: italic; margin-bottom: 6px;">"${escapeHtml(inc.desc)}"</div>` : ''}
            <div style="font-size: 11px; display: flex; gap: 12px; align-items: center;">
              <span>🔗 Source: <a href="${escapeHtml(inc.source_url)}" target="_blank" rel="noopener" style="color: var(--primary); text-decoration: underline;">${escapeHtml(inc.source_name || 'Wikipedia')} ↗</a></span>
            </div>
          `;
          if (flagBox) flagBox.style.display = 'none';
        } else if (isRaise) {
          flagBanner.className = 'flag-banner-raise';
          const recent = details.recent_incidents || [];
          const daysSince = recent.length > 0 ? `${recent[0].days_ago} days since last recorded incident` : 'No recent incidents triggered half-staff alert';
          flagBanner.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <strong style="color: var(--success); font-size: 13px; display: flex; align-items: center; gap: 6px;">
                <span>🏳️</span> FULL-STAFF (NORMAL)
              </strong>
              <span class="badge badge-success">Full-Staff</span>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
              Flags fly at full-staff. ${daysSince}.
            </div>
          `;
          if (flagBox) flagBox.style.display = 'none';
        } else {
          flagBanner.style.display = 'none';
          if (flagBox) flagBox.style.display = 'block';
        }
      }

      // Populate recent incidents table
      if (flagTbody && details.recent_incidents && details.recent_incidents.length > 0) {
        flagTbody.innerHTML = details.recent_incidents.map(inc => `
          <tr>
            <td style="white-space: nowrap; font-weight: 500;">${escapeHtml(inc.date)}</td>
            <td>${escapeHtml(inc.location)}</td>
            <td style="font-weight: 600; color: ${inc.dead > 0 ? 'var(--danger)' : 'inherit'};">${inc.dead}</td>
            <td>${inc.injured}</td>
            <td>${inc.total}</td>
            <td style="max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(inc.desc || '')}">
              ${escapeHtml(inc.desc || '—')}
            </td>
            <td style="white-space: nowrap;">
              <a href="${escapeHtml(inc.source_url)}" target="_blank" rel="noopener" style="color: var(--primary); font-size: 11px;">
                ${escapeHtml(inc.source_name || 'Article')} ↗
              </a>
            </td>
          </tr>
        `).join('');
      }

      // Telegram info
      const tgStatus = document.getElementById('telegram-status-label');
      const tg = data.telegram || {};
      const pauseBanner = document.getElementById('global-pause-banner');
      const pauseTimer = document.getElementById('global-pause-timer');

      if (!tg.configured) {
        tgStatus.textContent = 'No Bot Token';
        tgStatus.className = 'bot-state text-muted';
        if (pauseBanner) pauseBanner.classList.remove('show');
      } else if (!tg.enabled) {
        tgStatus.textContent = '🔴 Disabled';
        tgStatus.className = 'bot-state text-danger';
        if (pauseBanner) {
          pauseBanner.classList.add('show');
          if (pauseTimer) pauseTimer.textContent = 'Indefinitely (Disabled)';
        }
      } else if (tg.is_paused) {
        const remMins = Math.ceil((tg.pause_remaining_seconds || 0) / 60);
        tgStatus.textContent = `⏸️ Paused (${remMins}m)`;
        tgStatus.className = 'bot-state text-warning';
        if (pauseBanner) {
          pauseBanner.classList.add('show');
          if (pauseTimer) pauseTimer.textContent = `${remMins}m`;
        }
      } else {
        tgStatus.textContent = 'Active (Ready)';
        tgStatus.className = 'bot-state';
        if (pauseBanner) pauseBanner.classList.remove('show');
      }

      // Uptime
      const mins = Math.floor(data.uptime_seconds / 60);
      const hours = Math.floor(mins / 60);
      document.getElementById('uptime-label').textContent = hours > 0 ? `${hours}h ${mins % 60}m` : `${mins}m`;

    } catch (e) {
      console.error('Failed to load status:', e);
    }
  }

  function renderDashboardFeatureTiles() {
    const container = document.getElementById('dashboard-features-grid');
    if (!container) return;

    const data = latestStatusData || {};
    const featSummary = data.features_summary || {};
    const featKeys = Object.keys(featureMeta);

    // Merge all feature keys in clean display order
    const allKnownKeys = Array.from(new Set([
      'device_monitor',
      'network_discovery',
      'external_ip',
      'flag_status',
      'presence',
      'speedtest',
      'ssl_cert',
      'cisco_snmp',
      'ups_monitor',
      'access_logs',
      'webhooks',
      'night_owl',
      'photolevel',
      ...Object.keys(allFeatures || {}),
      ...featKeys
    ]));

    let activeCount = 0;
    allKnownKeys.forEach(k => {
      const fcfg = allFeatures[k];
      if (fcfg && fcfg.enabled !== false) activeCount++;
    });

    const chipCountAll = document.getElementById('dash-chip-count-all');
    const chipCountActive = document.getElementById('dash-chip-count-active');
    if (chipCountAll) chipCountAll.textContent = allKnownKeys.length;
    if (chipCountActive) chipCountActive.textContent = activeCount;

    // Filter features
    const visibleKeys = allKnownKeys.filter(k => {
      const fcfg = allFeatures[k] || {};
      const meta = featureMeta[k] || {};
      const isEnabled = fcfg.enabled !== false;
      const cat = meta.category || 'other';

      if (dashFeatureFilter === 'all') return true;
      if (dashFeatureFilter === 'active') return isEnabled;
      return cat === dashFeatureFilter;
    });

    if (visibleKeys.length === 0) {
      container.innerHTML = `<div style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--text-muted);">No monitoring features matching filter "<strong>${escapeHtml(dashFeatureFilter)}</strong>"</div>`;
      return;
    }

    container.innerHTML = visibleKeys.map(k => {
      const fcfg = allFeatures[k] || { enabled: false, interval_seconds: 300, notify_mode: 'on_change' };
      const meta = featureMeta[k] || {
        title: k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        icon: '⚙️',
        category: 'other'
      };
      const summaryInfo = featSummary[k] || {};
      const isEnabled = fcfg.enabled !== false;

      // Status Badge & Class
      let badgeText = isEnabled ? '● Active' : '○ Disabled';
      let badgeClass = isEnabled ? 'badge-success' : 'badge-muted';

      // Feature-specific live values
      let headlineHtml = '';
      let detailHtml = '';
      let quickActionHtml = '';

      if (k === 'device_monitor') {
        const total = (data.devices && data.devices.total) !== undefined ? data.devices.total : allDevices.length;
        const up = (data.devices && data.devices.up !== undefined) ? data.devices.up : total;
        const down = (data.devices && data.devices.down !== undefined) ? data.devices.down : 0;
        if (!isEnabled) {
          headlineHtml = 'Disabled';
          badgeClass = 'badge-muted';
          badgeText = '○ Disabled';
          detailHtml = 'Device ping and service checks inactive';
        } else if (down > 0) {
          headlineHtml = `<span style="color:var(--danger)">${down} DOWN</span> <span style="font-size:13px; font-weight:normal; color:var(--text-muted);">(${up}/${total} UP)</span>`;
          badgeClass = 'badge-danger';
          badgeText = `▲ ${down} DOWN`;
          detailHtml = `${up} of ${total} hosts reachable • Services degraded`;
        } else {
          headlineHtml = `<span>All Hosts UP (${up}/${total})</span>`;
          badgeClass = 'badge-success';
          badgeText = '● UP';
          const srvCount = (data.services && data.services.total) !== undefined ? data.services.total : allServices.length;
          detailHtml = `${up} hosts reachable • ${srvCount} services verified`;
        }
        quickActionHtml = `<button type="button" class="btn btn-secondary btn-sm btn-tile-nav" data-nav="devices" title="View device inventory">View Inventory ➔</button>`;
      } else if (k === 'network_discovery') {
        const totalKnown = (data.network_discovery && data.network_discovery.total_known) || 0;
        const onlineCount = (data.network_discovery && data.network_discovery.online_count) || 0;
        if (!isEnabled) {
          headlineHtml = 'Disabled';
          detailHtml = 'Subnet ARP scan and host discovery inactive';
        } else {
          headlineHtml = `<span>${onlineCount} Hosts Online</span>`;
          detailHtml = `${totalKnown} total hosts active in ARP cache`;
          quickActionHtml = `<button type="button" class="btn btn-secondary btn-sm btn-tile-scan" title="Sweep subnet for active hosts">🔍 Scan Subnet</button>`;
        }
      } else if (k === 'external_ip') {
        const ip = data.external_ip || summaryInfo.headline || 'Checking...';
        if (!isEnabled) {
          headlineHtml = 'Disabled';
          detailHtml = 'Public IP address monitoring inactive';
        } else {
          headlineHtml = `<code class="mono" style="font-size:15px; font-weight:700;">${escapeHtml(ip)}</code>`;
          detailHtml = 'Public WAN IP • Change notification active';
          quickActionHtml = `<button type="button" class="btn btn-secondary btn-sm btn-tile-refresh-ip" title="Check public IP now">↻ Check WAN</button>`;
        }
      } else if (k === 'flag_status') {
        const flagDetails = data.flag_status_details || {};
        const isLower = flagDetails.status_type === 'LOWER' || (data.flag_status && data.flag_status.includes('Lower Flag'));
        const recents = flagDetails.recent_incidents || [];
        const daysAgo = recents.length > 0 ? recents[0].days_ago : null;
        if (!isEnabled) {
          headlineHtml = 'Disabled';
          badgeClass = 'badge-muted';
          badgeText = '○ Disabled';
          detailHtml = 'Flag half-staff tracking inactive';
        } else if (isLower) {
          headlineHtml = `<span style="color:var(--danger)">🔻 Half-Staff Alert</span>`;
          badgeClass = 'badge-danger';
          badgeText = '🔻 Half-Staff';
          detailHtml = `Flags ordered to half-staff • ${daysAgo !== null ? daysAgo + 'd ago' : 'active incident'}`;
          quickActionHtml = `<button type="button" class="btn btn-secondary btn-sm btn-tile-flag-check" title="Check flag status now">⚡ Check Flag</button>`;
        } else {
          headlineHtml = `<span style="color:var(--success)">🏳️ Full-Staff (Normal)</span>`;
          badgeClass = 'badge-success';
          badgeText = '🏳️ Full-Staff';
          detailHtml = `Flags fly at full-staff • ${daysAgo !== null ? daysAgo + ' days since incident' : 'sources checked'}`;
          quickActionHtml = `<button type="button" class="btn btn-secondary btn-sm btn-tile-flag-check" title="Check flag status now">⚡ Check Flag</button>`;
        }
      } else if (k === 'presence') {
        const pres = data.presence || {};
        const home = pres.residents_home || 0;
        const total = pres.residents_total || 0;
        if (!isEnabled) {
          headlineHtml = 'Disabled';
          badgeClass = 'badge-muted';
          badgeText = '○ Disabled';
          detailHtml = 'Resident presence monitoring inactive';
        } else if (home > 0) {
          headlineHtml = `<span style="color:var(--success)">${home} of ${total} Residents Home</span>`;
          badgeClass = 'badge-success';
          badgeText = '● Home';
          detailHtml = 'Wi-Fi MAC tracking active • Arrival/departure alerts';
          quickActionHtml = `<button type="button" class="btn btn-secondary btn-sm btn-tile-presence-check" title="Check presence now">↻ Check Wi-Fi</button>`;
        } else {
          headlineHtml = `<span>0 of ${total} Residents Home</span>`;
          badgeClass = 'badge-warning';
          badgeText = '○ Away';
          detailHtml = 'All resident devices currently away from network';
          quickActionHtml = `<button type="button" class="btn btn-secondary btn-sm btn-tile-presence-check" title="Check presence now">↻ Check Wi-Fi</button>`;
        }
      } else if (k === 'ssl_cert') {
        if (!isEnabled) {
          headlineHtml = 'Disabled';
          detailHtml = 'SSL certificate expiration checking inactive';
        } else if (summaryInfo.status_badge === 'WARNING') {
          headlineHtml = `<span style="color:var(--warning)">${escapeHtml(summaryInfo.headline || 'Expiring Soon')}</span>`;
          badgeClass = 'badge-warning';
          badgeText = '▲ Expiring';
          detailHtml = 'Certificates expiring within warning threshold';
          quickActionHtml = `<button type="button" class="btn btn-secondary btn-sm btn-tile-ssl-check" title="Probe SSL certificates now">🔒 Probe Certs</button>`;
        } else {
          headlineHtml = `<span>All Certificates Valid</span>`;
          badgeClass = 'badge-success';
          badgeText = '● Valid';
          detailHtml = `TLS/HTTPS endpoints healthy • Warns at ${fcfg.options?.warning_days || 14}d`;
          quickActionHtml = `<button type="button" class="btn btn-secondary btn-sm btn-tile-ssl-check" title="Probe SSL certificates now">🔒 Probe Certs</button>`;
        }
      } else if (k === 'speedtest') {
        const cmp = summaryInfo.comparison;
        const curr = summaryInfo.current;
        const prev = summaryInfo.previous;
        let deltaHtml = '';
        if (curr && prev && cmp) {
          const dMb = cmp.download_delta_mbps;
          const dClass = dMb >= 0 ? 'text-success' : 'text-danger';
          const dSign = dMb >= 0 ? '+' : '';
          const dArrow = dMb >= 0 ? '↑' : '↓';
          deltaHtml = `<span class="${dClass}" style="font-size: 11px; margin-left: 6px; font-weight: 500;">(${dSign}${dMb} Mbps ${dArrow})</span>`;
        }
        if (!isEnabled) {
          headlineHtml = 'Disabled';
          detailHtml = 'Internet throughput and latency tests inactive';
        } else if (curr) {
          headlineHtml = `<span>${escapeHtml(summaryInfo.headline || '')}</span>${deltaHtml}`;
          detailHtml = escapeHtml(summaryInfo.detail || 'Throughput and latency monitoring');
          quickActionHtml = `
            <div style="display: flex; gap: 6px;">
              <button type="button" class="btn btn-secondary btn-sm btn-tile-speedtest-run" title="Run speedtest check now">⚡ Test</button>
              <button type="button" class="btn btn-secondary btn-sm btn-tile-speedtest-modal" title="View details and previous comparison">📊 Compare</button>
            </div>
          `;
        } else {
          headlineHtml = `<span>${escapeHtml(summaryInfo.headline || 'Scheduled')}</span>`;
          detailHtml = escapeHtml(summaryInfo.detail || 'Throughput and latency monitoring');
          quickActionHtml = `<button type="button" class="btn btn-secondary btn-sm btn-tile-speedtest-modal" title="Run speedtest and view comparison">⚡ Run Speedtest</button>`;
        }
      } else if (k === 'cisco_snmp') {
        if (!isEnabled) {
          headlineHtml = 'Disabled';
          detailHtml = 'Cisco SNMP switch monitoring inactive';
        } else {
          headlineHtml = `<span>${escapeHtml(fcfg.options?.device_id || 'core-switch')}</span>`;
          detailHtml = escapeHtml(summaryInfo.detail || 'Switch port link and saturation telemetry');
          quickActionHtml = `<button type="button" class="btn btn-secondary btn-sm btn-tile-cisco-check" title="Query switch SNMP now">🔀 Check Switch</button>`;
        }
      } else if (k === 'ups_monitor') {
        if (!isEnabled) {
          headlineHtml = 'Disabled';
          detailHtml = 'UPS power and battery monitoring inactive';
        } else {
          headlineHtml = `<span>${escapeHtml(summaryInfo.headline || 'Mains Power Normal')}</span>`;
          detailHtml = escapeHtml(summaryInfo.detail || 'AC circuit probe and battery backup monitor');
          quickActionHtml = `<button type="button" class="btn btn-secondary btn-sm btn-tile-ups-check" title="Query UPS status now">🔋 Check Battery</button>`;
        }
      } else if (k === 'access_logs') {
        headlineHtml = isEnabled ? '<span>SSH Audit Active</span>' : 'Disabled';
        detailHtml = `Audits auth.log • Trigger at ${fcfg.options?.failed_login_threshold || 3} failed logins`;
      } else if (k === 'webhooks') {
        headlineHtml = isEnabled ? '<span>Webhook Ingestion Ready</span>' : 'Disabled';
        detailHtml = 'POST /api/webhook/notify receiver active';
      } else if (k === 'night_owl') {
        headlineHtml = isEnabled ? `<span>${escapeHtml(fcfg.options?.quiet_start || '01:00')} – ${escapeHtml(fcfg.options?.quiet_end || '05:30')}</span>` : 'Disabled';
        detailHtml = 'Monitors kids and console activity during sleep hours';
      } else if (k === 'photolevel') {
        headlineHtml = isEnabled ? '<span>Ambient Light Sensor</span>' : 'Disabled';
        detailHtml = 'I2C ADC ambient illumination telemetry';
      } else {
        headlineHtml = isEnabled ? `<span>${escapeHtml(summaryInfo.headline || 'Active')}</span>` : 'Disabled';
        detailHtml = escapeHtml(summaryInfo.detail || meta.desc || '');
      }

      return `
        <div class="dashboard-feature-tile ${isEnabled ? 'is-enabled' : 'is-disabled'}" data-feature="${escapeHtml(k)}">
          <div class="dft-top">
            <div class="dft-title-group">
              <span class="dft-icon">${meta.icon || '⚙️'}</span>
              <h4 class="dft-name">${escapeHtml(meta.title)}</h4>
            </div>
            <span class="badge ${badgeClass} dft-badge">${badgeText}</span>
          </div>

          <div class="dft-body">
            <div class="dft-headline">${headlineHtml}</div>
            <div class="dft-subtext">${detailHtml}</div>
          </div>

          ${quickActionHtml ? `
          <div class="dft-footer">
            ${quickActionHtml}
          </div>` : ''}
        </div>
      `;
    }).join('');

    // Attach action button listeners (no config gear on tiles)
    container.querySelectorAll('.btn-tile-nav').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const tab = btn.getAttribute('data-nav');
        if (tab) navigateTo(tab);
      });
    });

    container.querySelectorAll('.btn-tile-scan').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        triggerScan();
      });
    });

    container.querySelectorAll('.btn-tile-refresh-ip').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const refreshBtn = document.getElementById('btn-refresh-ip');
        if (refreshBtn) refreshBtn.click();
      });
    });

    container.querySelectorAll('.btn-tile-flag-check').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const flagCheckBtn = document.getElementById('btn-dashboard-flag-check');
        if (flagCheckBtn) flagCheckBtn.click();
      });
    });

    container.querySelectorAll('.btn-tile-presence-check').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        btn.disabled = true;
        btn.textContent = '...';
        try {
          const res = await fetch('/api/presence/check', { method: 'POST' });
          const d = await res.json();
          if (d.success) {
            showToast('✓ Presence checked');
            await loadStatus();
          } else {
            showToast(`Presence check failed: ${d.error || 'Unknown'}`);
          }
        } catch (err) {
          showToast(`Presence check failed: ${err}`);
        } finally {
          btn.disabled = false;
          btn.textContent = '↻ Check';
        }
      });
    });

    container.querySelectorAll('.btn-tile-ssl-check').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        btn.disabled = true;
        btn.textContent = '...';
        try {
          const res = await fetch('/api/ssl/check', { method: 'POST' });
          const d = await res.json();
          if (d.success) {
            showToast('✓ SSL certificates audited');
            await loadStatus();
          } else {
            showToast(`SSL check failed: ${d.error || 'Unknown'}`);
          }
        } catch (err) {
          showToast(`SSL check failed: ${err}`);
        } finally {
          btn.disabled = false;
          btn.textContent = '🔒 Probe';
        }
      });
    });

    container.querySelectorAll('.btn-tile-speedtest-modal').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        openSpeedtestModal();
      });
    });

    container.querySelectorAll('.btn-tile-speedtest-run').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        runSpeedtest();
      });
    });

    container.querySelectorAll('.dashboard-feature-tile').forEach(tile => {
      tile.addEventListener('click', () => {
        const fname = tile.getAttribute('data-feature');
        if (fname === 'speedtest') {
          openSpeedtestModal();
        } else {
          openFeatureModal(fname);
        }
      });
    });

    container.querySelectorAll('.btn-tile-cisco-check').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        btn.disabled = true;
        btn.textContent = '...';
        try {
          const res = await fetch('/api/cisco/check', { method: 'POST' });
          const d = await res.json();
          if (d.success) {
            showToast('✓ Cisco SNMP ports checked');
            await loadStatus();
          } else {
            showToast(`Cisco check failed: ${d.error || 'Unknown'}`);
          }
        } catch (err) {
          showToast(`Cisco check failed: ${err}`);
        } finally {
          btn.disabled = false;
          btn.textContent = '🔀 Check';
        }
      });
    });

    container.querySelectorAll('.btn-tile-ups-check').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        btn.disabled = true;
        btn.textContent = '...';
        try {
          const res = await fetch('/api/ups/check', { method: 'POST' });
          const d = await res.json();
          if (d.success) {
            showToast('✓ UPS status checked');
            await loadStatus();
          } else {
            showToast(`UPS check failed: ${d.error || 'Unknown'}`);
          }
        } catch (err) {
          showToast(`UPS check failed: ${err}`);
        } finally {
          btn.disabled = false;
          btn.textContent = '🔋 Check';
        }
      });
    });
  }

  async function loadDevices() {
    try {
      const res = await fetch('/api/devices');
      const data = await res.json();
      if (!data.success) return;
      allDevices = data.devices || [];
      renderDevicesTable();
      renderSnapshotTable();
      if (formSrvDevice) {
        populateDeviceDropdown(formSrvDevice.value || (allDevices.length ? allDevices[0].id : ''));
      }
    } catch (e) {
      console.error('Failed to load devices:', e);
    }
  }

  function renderSnapshotTable() {
    const tbody = document.getElementById('snapshot-device-tbody');
    if (!allDevices.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No devices configured in devices.yaml</td></tr>';
      return;
    }

    tbody.innerHTML = allDevices.map(dev => {
      const statusBadge = dev.status === 'UP' 
        ? '<span class="badge badge-success">● UP</span>' 
        : (dev.status === 'DOWN' ? '<span class="badge badge-danger">▲ DOWN</span>' : '<span class="badge badge-muted">? UNKNOWN</span>');

      const netCount = Object.keys(dev.services || {}).length;
      const sysCount = (dev.ssh && Array.isArray(dev.ssh.systemd_services)) ? dev.ssh.systemd_services.length : Object.keys(dev.systemd || {}).length;
      const totalCount = netCount + sysCount;
      const srvLabel = totalCount === 1 ? '1 service' : `${totalCount} services`;
      return `
        <tr>
          <td>${statusBadge}</td>
          <td><strong>${escapeHtml(dev.name)}</strong></td>
          <td><code>${escapeHtml(dev.ip)}</code></td>
          <td><code>${escapeHtml(dev.mac || '—')}</code></td>
          <td><span class="pill-tag">${srvLabel}</span></td>
          <td><span class="mono">${dev.status === 'UP' ? '< 5ms' : '—'}</span></td>
        </tr>
      `;
    }).join('');
  }

  // --- Table Sorting Helpers ---
  function compareIPs(ipA, ipB) {
    const numA = (ipA || '').split('.').map(n => parseInt(n, 10) || 0);
    const numB = (ipB || '').split('.').map(n => parseInt(n, 10) || 0);
    for (let i = 0; i < 4; i++) {
      const a = numA[i] !== undefined ? numA[i] : 0;
      const b = numB[i] !== undefined ? numB[i] : 0;
      if (a !== b) return a - b;
    }
    return 0;
  }

  function compareValues(valA, valB, col, asc = true) {
    if (col === 'ip') {
      const cmp = compareIPs(valA, valB);
      return asc ? cmp : -cmp;
    }

    if (valA === undefined || valA === null) valA = '';
    if (valB === undefined || valB === null) valB = '';

    if (typeof valA === 'boolean' || typeof valB === 'boolean') {
      const numA = valA ? 1 : 0;
      const numB = valB ? 1 : 0;
      return asc ? numA - numB : numB - numA;
    }

    if (typeof valA === 'number' && typeof valB === 'number') {
      return asc ? valA - valB : valB - valA;
    }

    const strA = String(valA).toLowerCase();
    const strB = String(valB).toLowerCase();
    const cmp = strA.localeCompare(strB, undefined, { numeric: true });
    return asc ? cmp : -cmp;
  }

  function updateTableSortHeaders(tableId, sortState) {
    const table = document.getElementById(tableId);
    if (!table) return;
    table.querySelectorAll('th.sortable').forEach(th => {
      const col = th.getAttribute('data-sort');
      const icon = th.querySelector('.sort-icon');
      if (col === sortState.column) {
        th.className = `sortable ${sortState.asc ? 'sorted-asc' : 'sorted-desc'}`;
        if (icon) icon.textContent = sortState.asc ? '▲' : '▼';
      } else {
        th.className = 'sortable';
        if (icon) icon.textContent = '⇅';
      }
    });
  }

  function renderDevicesTable() {
    const tbody = document.getElementById('devices-tbody');
    const query = (devicesSearchInput.value || '').toLowerCase().trim();

    const filtered = allDevices.filter(d => {
      if (!query) return true;
      return (
        d.name.toLowerCase().includes(query) ||
        d.ip.toLowerCase().includes(query) ||
        (d.mac && d.mac.toLowerCase().includes(query)) ||
        d.tags.some(t => t.toLowerCase().includes(query))
      );
    });

    // Apply Sorting
    filtered.sort((a, b) => {
      let valA, valB;
      if (devicesSort.column === 'status') {
        valA = a.status;
        valB = b.status;
      } else if (devicesSort.column === 'name') {
        valA = a.name;
        valB = b.name;
      } else if (devicesSort.column === 'ip') {
        valA = a.ip;
        valB = b.ip;
      } else if (devicesSort.column === 'mac') {
        valA = a.mac;
        valB = b.mac;
      } else if (devicesSort.column === 'tags') {
        valA = (a.tags || []).join(',');
        valB = (b.tags || []).join(',');
      } else if (devicesSort.column === 'monitors') {
        const sysA = (a.ssh && Array.isArray(a.ssh.systemd_services)) ? a.ssh.systemd_services.length : Object.keys(a.systemd || {}).length;
        const sysB = (b.ssh && Array.isArray(b.ssh.systemd_services)) ? b.ssh.systemd_services.length : Object.keys(b.systemd || {}).length;
        valA = Object.keys(a.services || {}).length + sysA;
        valB = Object.keys(b.services || {}).length + sysB;
      } else if (devicesSort.column === 'last_check') {
        valA = a.last_check || 0;
        valB = b.last_check || 0;
      }
      return compareValues(valA, valB, devicesSort.column, devicesSort.asc);
    });

    updateTableSortHeaders('devices-table', devicesSort);

    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No matching devices found</td></tr>';
      return;
    }

    tbody.innerHTML = filtered.map(dev => {
      const statusBadge = dev.status === 'UP' 
        ? '<span class="badge badge-success">UP</span>' 
        : (dev.status === 'DOWN' ? '<span class="badge badge-danger">DOWN</span>' : '<span class="badge badge-muted">UNKNOWN</span>');

      const tagsPills = (dev.tags || []).map(t => `<span class="pill-tag">${escapeHtml(t)}</span>`).join('');
      
      const monitors = [];
      if (dev.ping_enabled) monitors.push('<span class="pill-tag">Ping</span>');
      const netCount = Object.keys(dev.services || {}).length;
      if (netCount > 0) monitors.push(`<span class="pill-tag">${netCount} Port Svc</span>`);
      const sysCount = (dev.ssh && Array.isArray(dev.ssh.systemd_services)) ? dev.ssh.systemd_services.length : Object.keys(dev.systemd || {}).length;
      if (sysCount > 0) monitors.push(`<span class="pill-tag">${sysCount} Systemd</span>`);
      if (dev.ssh_enabled) monitors.push('<span class="pill-tag">SSH</span>');
      if (dev.snmp_enabled) monitors.push('<span class="pill-tag">SNMP</span>');
      if (dev.prometheus_enabled) monitors.push('<span class="pill-tag">Prom</span>');

      const lastCheckedStr = dev.last_check > 0 ? new Date(dev.last_check * 1000).toLocaleTimeString() : 'Never';

      return `
        <tr>
          <td>${statusBadge}</td>
          <td><strong>${escapeHtml(dev.name)}</strong></td>
          <td><code>${escapeHtml(dev.ip)}</code></td>
          <td><code>${escapeHtml(dev.mac || '—')}</code></td>
          <td>${tagsPills || '<span class="text-muted">—</span>'}</td>
          <td>${monitors.join('')}</td>
          <td><span class="text-muted">${lastCheckedStr}</span></td>
          <td>
            <div style="display: flex; gap: 4px;">
              <button class="btn btn-secondary btn-sm btn-edit-device" data-id="${escapeHtml(dev.id)}" title="Edit device properties">Edit</button>
              <button class="btn btn-secondary btn-sm btn-device-add-service" data-id="${escapeHtml(dev.id)}" title="Add a service/port to this device">+ Svc</button>
              <button class="btn btn-secondary btn-sm btn-delete-device" data-id="${escapeHtml(dev.id)}" title="Delete device">Delete</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    // Attach edit device listener
    tbody.querySelectorAll('.btn-edit-device').forEach(btn => {
      btn.addEventListener('click', () => {
        const devId = btn.getAttribute('data-id');
        const dev = allDevices.find(d => d.id === devId);
        if (dev) openDeviceModal(dev);
      });
    });

    // Attach add-service to device listener
    tbody.querySelectorAll('.btn-device-add-service').forEach(btn => {
      btn.addEventListener('click', () => {
        const devId = btn.getAttribute('data-id');
        openServiceModalForDevice(devId);
      });
    });

    // Attach delete listeners
    tbody.querySelectorAll('.btn-delete-device').forEach(btn => {
      btn.addEventListener('click', async () => {
        const devId = btn.getAttribute('data-id');
        if (!confirm(`Are you sure you want to remove device '${devId}' from devices.yaml?`)) return;
        try {
          const res = await fetch(`/api/devices/${devId}`, { method: 'DELETE' });
          const data = await res.json();
          if (data.success) {
            showToast(`Device '${devId}' removed`);
            await loadDevices();
            await loadStatus();
          } else {
            showToast(`Error: ${data.error}`);
          }
        } catch (e) {
          showToast(`Request failed: ${e}`);
        }
      });
    });
  }

  async function loadDiscovery() {
    try {
      const res = await fetch('/api/discovery');
      const data = await res.json();
      if (!data.success) return;
      allDiscovery = data.hosts;
      renderDiscoveryTable();
    } catch (e) {
      console.error('Failed to load discovery:', e);
    }
  }

  function renderDiscoveryTable() {
    const tbody = document.getElementById('discovery-tbody');
    const query = (discoverySearchInput.value || '').toLowerCase().trim();

    const filtered = allDiscovery.filter(h => {
      if (!query) return true;
      return (
        h.ip.toLowerCase().includes(query) ||
        h.mac.toLowerCase().includes(query) ||
        (h.vendor && h.vendor.toLowerCase().includes(query)) ||
        (h.hostname && h.hostname.toLowerCase().includes(query))
      );
    });

    // Apply Sorting
    filtered.sort((a, b) => {
      let valA, valB;
      if (discoverySort.column === 'online') {
        valA = a.online !== false;
        valB = b.online !== false;
      } else if (discoverySort.column === 'ip') {
        valA = a.ip;
        valB = b.ip;
      } else if (discoverySort.column === 'mac') {
        valA = a.mac;
        valB = b.mac;
      } else if (discoverySort.column === 'vendor') {
        valA = a.vendor || '';
        valB = b.vendor || '';
      } else if (discoverySort.column === 'hostname') {
        valA = a.hostname || '';
        valB = b.hostname || '';
      } else if (discoverySort.column === 'is_configured') {
        valA = a.is_configured ? 1 : 0;
        valB = b.is_configured ? 1 : 0;
      }
      return compareValues(valA, valB, discoverySort.column, discoverySort.asc);
    });

    updateTableSortHeaders('discovery-table', discoverySort);

    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No discovered hosts in ARP cache. Click "Trigger Subnet Scan" above.</td></tr>';
      return;
    }

    tbody.innerHTML = filtered.map(h => {
      const isOnline = h.online !== false;
      const stateBadge = isOnline 
        ? '<span class="badge badge-success">ACTIVE</span>' 
        : '<span class="badge badge-muted">OFFLINE</span>';

      const isKnown = h.is_configured;
      const classification = isKnown 
        ? `<span class="badge badge-primary">Configured (${escapeHtml(h.custom_name || 'Device')})</span>` 
        : '<span class="badge badge-warning">Unmonitored</span>';

      const actionBtn = isKnown 
        ? '<span class="text-muted">In Inventory</span>' 
        : `<button class="btn btn-secondary btn-sm btn-quick-add" data-ip="${escapeHtml(h.ip)}" data-mac="${escapeHtml(h.mac)}" data-vendor="${escapeHtml(h.vendor || '')}">+ Monitor</button>`;

      return `
        <tr>
          <td>${stateBadge}</td>
          <td><code>${escapeHtml(h.ip)}</code></td>
          <td><code>${escapeHtml(h.mac)}</code></td>
          <td><strong>${escapeHtml(h.vendor || 'Unknown Vendor')}</strong></td>
          <td><span class="text-muted">${escapeHtml(h.hostname || 'No PTR Record')}</span></td>
          <td>${classification}</td>
          <td>${actionBtn}</td>
        </tr>
      `;
    }).join('');

    // Attach quick add listeners
    tbody.querySelectorAll('.btn-quick-add').forEach(btn => {
      btn.addEventListener('click', () => {
        const ip = btn.getAttribute('data-ip');
        const mac = btn.getAttribute('data-mac');
        const vendor = btn.getAttribute('data-vendor');

        openDeviceModal({
          id: `device-${ip.replace(/\./g, '-')}`,
          name: vendor ? `${vendor} Device` : `Device ${ip}`,
          ip: ip,
          mac: mac,
          tags: ['lan'],
          ping_enabled: true,
          ping_timeout: 2.0,
        });
      });
    });
  }

  async function loadServices() {
    try {
      const res = await fetch('/api/services');
      const data = await res.json();
      if (!data.success) return;
      allServices = data.services || [];
      renderServicesTable();
    } catch (e) {
      console.error('Failed to load services:', e);
    }
  }

  function renderServicesTable() {
    const tbody = document.getElementById('services-tbody');
    const query = (servicesSearchInput ? servicesSearchInput.value : '').toLowerCase().trim();

    const filtered = allServices.filter(s => {
      if (!query) return true;
      return (
        s.service_name.toLowerCase().includes(query) ||
        s.device_name.toLowerCase().includes(query) ||
        s.device_ip.toLowerCase().includes(query) ||
        (s.hostname && s.hostname.toLowerCase().includes(query)) ||
        s.type.toLowerCase().includes(query) ||
        String(s.port).includes(query)
      );
    });

    // Apply Sorting
    filtered.sort((a, b) => {
      let valA = a[servicesSort.column];
      let valB = b[servicesSort.column];
      return compareValues(valA, valB, servicesSort.column, servicesSort.asc);
    });

    updateTableSortHeaders('services-table', servicesSort);

    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No services found. Click "+ Add Monitored Service & Port" above to add one.</td></tr>';
      return;
    }

    tbody.innerHTML = filtered.map(s => {
      const isSystemd = (s.type === 'systemd');
      const statusBadge = s.status === 'UP' 
        ? `<span class="badge badge-success">● UP${isSystemd ? ' (active)' : ''}</span>` 
        : (s.status === 'DOWN' ? `<span class="badge badge-danger">▲ DOWN${isSystemd ? ' (inactive)' : ''}</span>` : '<span class="badge badge-warning">? UNKNOWN</span>');

      const latStr = (!isSystemd && s.latency_ms > 0) ? `${s.latency_ms.toFixed(1)} ms` : (isSystemd && s.latency_ms > 0 ? `${s.latency_ms.toFixed(0)} ms` : '—');
      const typeBadge = isSystemd
        ? '<span class="pill-tag" style="background: rgba(14, 165, 233, 0.15); color: #0284c7; border: 1px solid rgba(14, 165, 233, 0.3);">SYSTEMD</span>'
        : `<span class="pill-tag">${s.type.toUpperCase()}</span>`;
      const portOrTarget = isSystemd
        ? `<code class="text-muted" style="font-size:11px;">systemctl</code>`
        : `:<strong>${s.port}</strong>`;
      const pathInfo = (s.type === 'http' || s.type === 'https') ? ` <code class="text-muted" style="font-size:11px;">${escapeHtml(s.path || '/')}</code>` : '';
      const hostPill = s.hostname ? `<div style="font-size:11px; color: var(--primary); margin-top:2px;">🌐 <strong>${escapeHtml(s.hostname)}</strong></div>` : '';
      const sslPill = s.check_ssl ? `<span class="pill-tag" style="background: rgba(16, 185, 129, 0.15); color: #059669; border: 1px solid rgba(16, 185, 129, 0.3); font-size:10px; margin-left:4px;" title="TLS Certificate Expiration Monitored">🔒 TLS</span>` : '';

      return `
        <tr data-service-id="${escapeHtml(s.service_name)}" data-device-id="${escapeHtml(s.device_id)}">
          <td>${statusBadge}</td>
          <td><strong>${escapeHtml(s.service_name)}</strong></td>
          <td>${escapeHtml(s.device_name)} <br><code class="text-muted" style="font-size:11px;">${escapeHtml(s.device_ip)}</code></td>
          <td>${typeBadge} ${portOrTarget}${pathInfo}${sslPill}${hostPill}</td>
          <td><span class="mono">${latStr}</span></td>
          <td><span class="text-muted" style="font-size: 12px;">${escapeHtml(s.message)}</span></td>
          <td>
            <div style="display: flex; gap: 4px;">
              <button class="btn btn-secondary btn-sm btn-probe-service" data-dev="${escapeHtml(s.device_id)}" data-srv="${escapeHtml(s.service_name)}" title="Test probe now">⚡ Test</button>
              <button class="btn btn-secondary btn-sm btn-edit-service" data-dev="${escapeHtml(s.device_id)}" data-srv="${escapeHtml(s.service_name)}" title="Edit service">Edit</button>
              <button class="btn btn-secondary btn-sm btn-delete-service" data-dev="${escapeHtml(s.device_id)}" data-srv="${escapeHtml(s.service_name)}" title="Delete service">Delete</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    // Attach Edit button listeners
    tbody.querySelectorAll('.btn-edit-service').forEach(btn => {
      btn.addEventListener('click', () => {
        const devId = btn.getAttribute('data-dev');
        const srvName = btn.getAttribute('data-srv');
        const srvData = allServices.find(s => s.device_id === devId && s.service_name === srvName);
        if (srvData) {
          openServiceModalForDevice(devId, srvData);
        }
      });
    });

    // Attach Delete button listeners
    tbody.querySelectorAll('.btn-delete-service').forEach(btn => {
      btn.addEventListener('click', async () => {
        const devId = btn.getAttribute('data-dev');
        const srvName = btn.getAttribute('data-srv');
        if (!confirm(`Are you sure you want to delete service '${srvName}' from device '${devId}'?`)) return;

        try {
          const res = await fetch('/api/services', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_id: devId, service_name: srvName })
          });
          const data = await res.json();
          if (data.success) {
            showToast(`Service '${srvName}' deleted`);
            await loadServices();
            await loadDevices();
            await loadStatus();
          } else {
            showToast(`Delete failed: ${data.error}`);
          }
        } catch (e) {
          showToast(`Delete error: ${e}`);
        }
      });
    });

    // Attach Probe button listeners
    tbody.querySelectorAll('.btn-probe-service').forEach(btn => {
      btn.addEventListener('click', async () => {
        const devId = btn.getAttribute('data-dev');
        const srvName = btn.getAttribute('data-srv');
        const srvData = allServices.find(s => s.device_id === devId && s.service_name === srvName);
        if (!srvData) return;

        btn.disabled = true;
        btn.textContent = '...';
        try {
          const res = await fetch('/api/services/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              device_id: devId,
              service_name: srvName,
              ip: srvData.device_ip,
              type: srvData.type,
              port: srvData.port,
              hostname: srvData.hostname || '',
              check_ssl: !!srvData.check_ssl,
              path: srvData.path,
              expected_status: srvData.expected_status,
              timeout: srvData.timeout || 3.0
            })
          });
          const data = await res.json();
          if (data.success && data.result) {
            const r = data.result;
            // Instantly update in-memory item so table reflects probe result
            srvData.status = r.status;
            srvData.latency_ms = r.latency_ms;
            srvData.message = r.message;
            renderServicesTable();
            showToast(`${srvName}: ${r.status} (${r.latency_ms.toFixed(1)} ms) - ${r.message}`);
            await loadServices();
            await loadDevices();
          } else {
            showToast(`Test error: ${data.error || 'Failed'}`);
          }
        } catch (e) {
          showToast(`Probe error: ${e}`);
        } finally {
          btn.disabled = false;
          btn.textContent = '⚡ Test';
        }
      });
    });
  }

  // Service Modal helpers & Discovered Services
  let discoveredServicesCache = {};
  let currentDiscoveredServices = [];

  function populateDeviceDropdown(selectedDevId = '') {
    if (!formSrvDevice) return;
    if (!allDevices || allDevices.length === 0) {
      formSrvDevice.innerHTML = '<option value="">-- No devices configured --</option>';
      return;
    }
    const targetId = selectedDevId || (formSrvDevice.value && allDevices.some(d => d.id === formSrvDevice.value) ? formSrvDevice.value : allDevices[0].id);
    formSrvDevice.innerHTML = allDevices.map(d => {
      const isSel = d.id === targetId ? 'selected' : '';
      return `<option value="${escapeHtml(d.id)}" ${isSel}>${escapeHtml(d.name)} (${escapeHtml(d.ip)})</option>`;
    }).join('');
    formSrvDevice.value = targetId;
  }

  function updateServiceTypeVisibility() {
    const t = formSrvType.value;
    const isSystemd = (t === 'systemd');
    const portGroup = document.getElementById('form-srv-port-group');
    if (portGroup) portGroup.style.display = isSystemd ? 'none' : 'block';
    if (formSrvPort) formSrvPort.required = !isSystemd;
    formSrvHttpOptions.style.display = (t === 'http' || t === 'https') ? 'block' : 'none';
    if (formSrvName) {
      formSrvName.placeholder = isSystemd ? 'e.g. ssh, docker, nginx, homeassistant' : 'e.g. Plex, Web Admin, SSH, MySQL';
    }
    if (btnTestServiceProbe) {
      btnTestServiceProbe.textContent = isSystemd ? '⚡ Test Service Now' : '⚡ Test Port Now';
    }
  }

  async function loadAvailableServices(devId, protocol, forceRefresh = false) {
    if (!formSrvDiscovered || !devId) return;

    const cacheKey = `${devId}:${protocol}`;
    formSrvDiscovered.disabled = true;
    formSrvDiscovered.innerHTML = `<option value="">🔍 Scanning host for ${escapeHtml(protocol)} services...</option>`;
    if (formSrvDiscoveryStatus) {
      formSrvDiscoveryStatus.textContent = 'Scanning host for running services and listening ports...';
      formSrvDiscoveryStatus.style.color = 'var(--text-muted)';
    }

    try {
      let data;
      if (!forceRefresh && discoveredServicesCache[cacheKey]) {
        data = discoveredServicesCache[cacheKey];
      } else {
        const url = `/api/devices/${encodeURIComponent(devId)}/available-services?type=${encodeURIComponent(protocol)}`;
        const res = await fetch(url);
        data = await res.json();
        if (data.success) {
          discoveredServicesCache[cacheKey] = data;
        }
      }

      if (!data || !data.success) {
        formSrvDiscovered.disabled = false;
        formSrvDiscovered.innerHTML = `<option value="">-- Could not scan host (${escapeHtml((data && data.error) || 'Failed')}) --</option><option value="__custom__">-- Enter service manually --</option>`;
        if (formSrvDiscoveryStatus) {
          formSrvDiscoveryStatus.textContent = `Scan failed: ${(data && data.error) || 'Device unreachable'}. Enter service details manually below.`;
          formSrvDiscoveryStatus.style.color = 'var(--warning-text, #f59e0b)';
        }
        return;
      }

      currentDiscoveredServices = data.services || [];
      formSrvDiscovered.disabled = false;
      formSrvDiscovered.innerHTML = '';

      if (currentDiscoveredServices.length === 0) {
        const emptyOpt = document.createElement('option');
        emptyOpt.value = '';
        emptyOpt.textContent = `-- No ${protocol} services found on host (enter manually below) --`;
        formSrvDiscovered.appendChild(emptyOpt);

        const customOpt = document.createElement('option');
        customOpt.value = '__custom__';
        customOpt.textContent = '-- Custom / Enter manually --';
        formSrvDiscovered.appendChild(customOpt);

        if (formSrvDiscoveryStatus) {
          if (protocol === 'systemd' && !data.ssh_enabled) {
            formSrvDiscoveryStatus.textContent = 'SSH telemetry is not enabled for this device. Enable SSH under Devices to discover systemd services.';
            formSrvDiscoveryStatus.style.color = 'var(--warning-text, #f59e0b)';
          } else {
            formSrvDiscoveryStatus.textContent = `No active ${protocol} services detected on ${data.ip}. Enter service details manually below.`;
            formSrvDiscoveryStatus.style.color = 'var(--text-muted)';
          }
        }
      } else {
        const defaultOpt = document.createElement('option');
        defaultOpt.value = '';
        defaultOpt.textContent = `-- Select a discovered service (${currentDiscoveredServices.length} available) --`;
        formSrvDiscovered.appendChild(defaultOpt);

        currentDiscoveredServices.forEach((s, idx) => {
          const opt = document.createElement('option');
          opt.value = String(idx);
          opt.textContent = s.label;
          formSrvDiscovered.appendChild(opt);
        });

        const customOpt = document.createElement('option');
        customOpt.value = '__custom__';
        customOpt.textContent = '-- Custom / Not in list (enter manually below) --';
        formSrvDiscovered.appendChild(customOpt);

        if (formSrvDiscoveryStatus) {
          formSrvDiscoveryStatus.textContent = `Discovered ${currentDiscoveredServices.length} service(s) on ${data.ip}. Select one to auto-fill.`;
          formSrvDiscoveryStatus.style.color = 'var(--success-text, #10b981)';
        }
      }

      // If formSrvName already has a value (e.g. editing), try matching in dropdown
      const currName = formSrvName ? formSrvName.value.trim().toLowerCase() : '';
      if (currName) {
        const matchIdx = currentDiscoveredServices.findIndex(s => s.name.toLowerCase() === currName || (s.name + ' (systemd)').toLowerCase() === currName);
        if (matchIdx >= 0) {
          formSrvDiscovered.value = String(matchIdx);
        }
      }
    } catch (err) {
      console.error('Error fetching available services:', err);
      formSrvDiscovered.disabled = false;
      formSrvDiscovered.innerHTML = `<option value="">-- Scan error (enter manually below) --</option><option value="__custom__">-- Enter service manually --</option>`;
      if (formSrvDiscoveryStatus) {
        formSrvDiscoveryStatus.textContent = `Scan error: ${err.message}. You can enter details manually below.`;
        formSrvDiscoveryStatus.style.color = 'var(--danger-text)';
      }
    }
  }

  async function openServiceModalForDevice(devId, serviceData = null, updateRoute = true) {
    if (updateRoute) {
      let sub = 'add';
      if (serviceData) {
        sub = `edit/${encodeURIComponent(serviceData.service_name)}`;
      } else if (devId) {
        sub = `add/${encodeURIComponent(devId)}`;
      }
      navigateTo('services', sub, true);
      return;
    }

    if (!allDevices || allDevices.length === 0) {
      await loadDevices();
    }

    serviceForm.reset();
    serviceProbeResult.textContent = 'Ready to test';
    serviceProbeResult.className = 'mono';
    serviceProbeResult.style.color = 'var(--text-muted)';

    const targetDevId = devId || (serviceData ? serviceData.device_id : (allDevices.length ? allDevices[0].id : ''));
    populateDeviceDropdown(targetDevId);

    if (serviceData) {
      serviceModalTitle.textContent = 'Edit Monitored Service & Port';
      formSrvOriginalName.value = serviceData.service_name;
      formSrvName.value = serviceData.service_name;
      formSrvDevice.value = serviceData.device_id;
      formSrvType.value = serviceData.type || 'tcp';
      formSrvPort.value = serviceData.port || 80;
      if (formSrvHostname) formSrvHostname.value = serviceData.hostname || '';
      if (formSrvCheckSsl) formSrvCheckSsl.checked = (serviceData.check_ssl !== undefined) ? !!serviceData.check_ssl : (serviceData.type === 'https' || serviceData.port === 443);
      formSrvPath.value = serviceData.path || '/';
      formSrvStatus.value = serviceData.expected_status || 200;
      formSrvTimeout.value = serviceData.timeout || 3.0;
    } else {
      serviceModalTitle.textContent = 'Add Monitored Service & Port';
      formSrvOriginalName.value = '';
      formSrvName.value = '';
      if (targetDevId) formSrvDevice.value = targetDevId;
      formSrvType.value = 'tcp';
      formSrvPort.value = 80;
      if (formSrvHostname) formSrvHostname.value = '';
      if (formSrvCheckSsl) formSrvCheckSsl.checked = true;
      formSrvPath.value = '/';
      formSrvStatus.value = 200;
      formSrvTimeout.value = 3.0;
    }

    updateServiceTypeVisibility();
    const activeDevId = formSrvDevice.value || targetDevId || (allDevices.length ? allDevices[0].id : '');
    const activeType = formSrvType.value || 'tcp';
    if (activeDevId) {
      loadAvailableServices(activeDevId, activeType);
    }
    serviceModal.classList.add('open');
  }

  function closeServiceModal() {
    if (serviceModal) serviceModal.classList.remove('open');
    if (window.location.hash.startsWith('#services/')) {
      navigateTo('services', null, true);
    } else {
      updateBreadcrumbs(currentTab, null);
    }
  }

  formSrvType.addEventListener('change', () => {
    updateServiceTypeVisibility();
    if (formSrvCheckSsl && formSrvType.value === 'https') {
      formSrvCheckSsl.checked = true;
    }
    const devId = formSrvDevice.value;
    if (devId) {
      loadAvailableServices(devId, formSrvType.value);
    }
  });

  formSrvDevice.addEventListener('change', () => {
    const devId = formSrvDevice.value;
    if (devId) {
      loadAvailableServices(devId, formSrvType.value);
    }
  });

  if (formSrvDiscovered) {
    formSrvDiscovered.addEventListener('change', () => {
      const val = formSrvDiscovered.value;
      if (val === '__custom__') {
        formSrvName.focus();
        return;
      }
      if (!val) return;
      const idx = parseInt(val, 10);
      if (isNaN(idx) || idx < 0 || idx >= currentDiscoveredServices.length) return;
      const s = currentDiscoveredServices[idx];
      if (!s) return;

      formSrvName.value = s.name;
      if (s.port && formSrvPort) {
        formSrvPort.value = s.port;
      }
      if (s.path && formSrvPath) {
        formSrvPath.value = s.path;
      }
      if (s.type && s.type !== formSrvType.value) {
        formSrvType.value = s.type;
        updateServiceTypeVisibility();
      }
      if (formSrvDiscoveryStatus) {
        formSrvDiscoveryStatus.textContent = `Selected: ${s.name} ${s.port ? `(Port ${s.port})` : ''} - details filled below.`;
        formSrvDiscoveryStatus.style.color = 'var(--primary)';
      }
    });
  }

  if (btnRefreshDiscoveredServices) {
    btnRefreshDiscoveredServices.addEventListener('click', (e) => {
      e.preventDefault();
      const devId = formSrvDevice.value;
      if (devId) {
        loadAvailableServices(devId, formSrvType.value, true);
      }
    });
  }

  if (servicesSearchInput) {
    servicesSearchInput.addEventListener('input', renderServicesTable);
  }

  btnOpenAddService.addEventListener('click', async () => {
    if (!allDevices || allDevices.length === 0) {
      await loadDevices();
    }
    openServiceModalForDevice('');
  });

  btnCloseServiceModal.addEventListener('click', closeServiceModal);
  btnCancelServiceModal.addEventListener('click', closeServiceModal);
  if (serviceModal) {
    serviceModal.addEventListener('click', (e) => {
      if (e.target === serviceModal) closeServiceModal();
    });
  }

  // Modal Service Test Probe Button
  btnTestServiceProbe.addEventListener('click', async () => {
    const devId = formSrvDevice.value;
    const targetDev = allDevices.find(d => d.id === devId);
    if (!targetDev) {
      serviceProbeResult.textContent = 'Select a valid device';
      serviceProbeResult.style.color = 'var(--danger-text)';
      return;
    }

    const type = formSrvType.value;
    const port = parseInt(formSrvPort.value, 10);
    const hostname = formSrvHostname ? formSrvHostname.value.trim() : '';
    const checkSsl = formSrvCheckSsl ? formSrvCheckSsl.checked : (type === 'https' || port === 443);
    const path = formSrvPath.value.trim() || '/';
    const status = parseInt(formSrvStatus.value, 10) || 200;
    const timeout = parseFloat(formSrvTimeout.value) || 3.0;

    if (type !== 'systemd' && (!port || port < 1 || port > 65535)) {
      serviceProbeResult.textContent = 'Enter valid port (1-65535)';
      serviceProbeResult.style.color = 'var(--danger-text)';
      return;
    }

    serviceProbeResult.textContent = 'Testing connection...';
    serviceProbeResult.style.color = 'var(--text-muted)';
    btnTestServiceProbe.disabled = true;

    try {
      const srvName = formSrvName.value.trim();
      const res = await fetch('/api/services/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          device_id: devId,
          service_name: srvName || undefined,
          ip: targetDev.ip,
          type,
          port,
          hostname,
          check_ssl: checkSsl,
          path,
          expected_status: status,
          timeout
        })
      });
      const data = await res.json();
      if (data.success && data.result) {
        const r = data.result;
        if (r.status === 'UP') {
          serviceProbeResult.textContent = `✓ UP (${r.latency_ms.toFixed(1)}ms) - ${r.message}`;
          serviceProbeResult.style.color = 'var(--success-text)';
        } else {
          serviceProbeResult.textContent = `✗ ${r.status}: ${r.message}`;
          serviceProbeResult.style.color = 'var(--danger-text)';
        }
        if (srvName) {
          await loadServices();
        }
      } else {
        serviceProbeResult.textContent = `Error: ${data.error || 'Failed'}`;
        serviceProbeResult.style.color = 'var(--danger-text)';
      }
    } catch (err) {
      serviceProbeResult.textContent = `Error: ${err}`;
      serviceProbeResult.style.color = 'var(--danger-text)';
    } finally {
      btnTestServiceProbe.disabled = false;
    }
  });

  // Modal Service Form Submission
  let isSavingService = false;
  async function handleSaveService(e) {
    if (e) e.preventDefault();
    if (isSavingService) return;

    const devId = formSrvDevice.value;
    const originalName = formSrvOriginalName.value.trim();
    let name = formSrvName.value.trim();
    const type = formSrvType.value;

    // If name is empty but a discovered service is selected, auto-fill it
    if (!name && formSrvDiscovered && formSrvDiscovered.value && formSrvDiscovered.value !== '__custom__') {
      const idx = parseInt(formSrvDiscovered.value, 10);
      if (!isNaN(idx) && currentDiscoveredServices && currentDiscoveredServices[idx]) {
        name = currentDiscoveredServices[idx].name;
        formSrvName.value = name;
      }
    }

    const port = type === 'systemd' ? 0 : (parseInt(formSrvPort.value, 10) || 0);
    const hostname = formSrvHostname ? formSrvHostname.value.trim() : '';
    const checkSsl = formSrvCheckSsl ? formSrvCheckSsl.checked : (type === 'https' || port === 443);
    const path = formSrvPath.value.trim() || '/';
    const status = parseInt(formSrvStatus.value, 10) || 200;
    const timeout = parseFloat(formSrvTimeout.value) || 3.0;

    if (!devId) {
      showToast('Please select a target device');
      return;
    }

    if (!name) {
      showToast('Service name is required');
      if (formSrvName) formSrvName.focus();
      return;
    }

    if (type !== 'systemd' && (!port || port < 1 || port > 65535)) {
      showToast('A valid port number (1-65535) is required');
      if (formSrvPort) formSrvPort.focus();
      return;
    }

    const payload = {
      device_id: devId,
      original_name: originalName,
      name,
      type,
      port,
      hostname,
      check_ssl: checkSsl,
      path,
      expected_status: status,
      timeout
    };

    const saveBtn = document.getElementById('btn-save-service-submit');
    isSavingService = true;
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';
    }

    try {
      const res = await fetch('/api/services', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        showToast(data.message || `Service '${name}' saved successfully`);
        closeServiceModal();
        await Promise.allSettled([
          loadServices(),
          loadDevices(),
          loadStatus()
        ]);
      } else {
        showToast(`Save failed: ${data.error || 'Unknown error'}`);
      }
    } catch (err) {
      showToast(`Request failed: ${err}`);
    } finally {
      isSavingService = false;
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Service';
      }
    }
  }

  serviceForm.addEventListener('submit', handleSaveService);

  async function loadResources() {
    const container = document.getElementById('resources-cards-container');
    const refreshIcon = document.getElementById('resources-refresh-icon');
    if (refreshIcon) refreshIcon.style.animation = 'spin 1s linear infinite';
    try {
      const res = await fetch('/api/resources');
      const data = await res.json();
      if (!data.success || !data.resources.length) {
        cachedResources = [];
        container.innerHTML = '<div class="card"><div class="card-body text-center text-muted">No telemetry received yet. Enable SSH monitoring on Linux devices in <code>devices.yaml</code> to view CPU, RAM, and Disk metrics.</div></div>';
        return;
      }

      cachedResources = data.resources;
      renderResourceCards();
    } catch (e) {
      console.error('Failed to load resources:', e);
    } finally {
      if (refreshIcon) refreshIcon.style.animation = '';
    }
  }

  function renderResourceCards() {
    const container = document.getElementById('resources-cards-container');
    if (!container) return;

    if (!cachedResources || !cachedResources.length) {
      container.innerHTML = '<div class="card"><div class="card-body text-center text-muted">No telemetry received yet. Enable SSH monitoring on Linux devices in <code>devices.yaml</code> to view CPU, RAM, and Disk metrics.</div></div>';
      return;
    }

    container.innerHTML = cachedResources.map(r => {
      const memPct = r.memory_percent || 0;
      const memClass = memPct > 90 ? 'crit' : (memPct > 75 ? 'warn' : 'normal');

      const diskBars = Object.entries(r.disk_usage || {}).map(([mount, pct]) => {
        const dClass = pct > 90 ? 'crit' : (pct > 75 ? 'warn' : 'normal');
        return `
          <div class="meter-group">
            <div class="meter-label">
              <span>Disk (${escapeHtml(mount)})</span>
              <strong>${pct}%</strong>
            </div>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill ${dClass}" style="width: ${Math.min(pct, 100)}%"></div>
            </div>
          </div>
        `;
      }).join('');

      const systemdBadges = Object.entries(r.systemd || {}).map(([srv, state]) => {
        const badgeClass = state === 'active' ? 'badge-success' : 'badge-danger';
        return `<span class="badge ${badgeClass}" style="margin: 2px;">${escapeHtml(srv)}: ${state}</span>`;
      }).join('');

      // Process Breakdown
      const currentProcTab = cardProcessTabs[r.device_id] || 'cpu';
      const procs = (currentProcTab === 'cpu' ? r.top_cpu_processes : r.top_mem_processes) || [];
      const top5Procs = procs.slice(0, 5);

      let procsHtml = '';
      if (top5Procs.length === 0) {
        procsHtml = `<div class="text-muted text-center" style="font-size: 11.5px; padding: 10px; background: var(--border-subtle); border-radius: 4px;">No process telemetry captured yet.</div>`;
      } else {
        procsHtml = `<div class="proc-mini-list">` + top5Procs.map(p => {
          const valBadge = currentProcTab === 'cpu'
            ? `<span class="proc-mini-val proc-val-cpu">${p.cpu_percent}% CPU</span>`
            : `<span class="proc-mini-val proc-val-mem">${p.mem_percent}% RAM</span>`;
          return `
            <div class="proc-mini-item" title="${escapeHtml(p.args || p.command)}">
              <div style="display: flex; align-items: center; gap: 6px; overflow: hidden; min-width: 0;">
                <span class="proc-mini-name">${escapeHtml(p.command)}</span>
                <span class="proc-mini-pid">#${p.pid}</span>
                <span style="font-size: 10px; color: var(--text-muted);">${escapeHtml(p.user)}</span>
              </div>
              <div style="flex-shrink: 0;">
                ${valBadge}
              </div>
            </div>
          `;
        }).join('') + `</div>`;
      }

      return `
        <div class="resource-card" id="res-card-${escapeHtml(r.device_id)}">
          <div class="resource-header">
            <div>
              <h3 style="margin: 0; font-size: 16px;">${escapeHtml(r.device_name)}</h3>
              <code class="text-muted" style="font-size: 11px;">${escapeHtml(r.device_ip)}</code>
            </div>
            <span class="badge badge-primary">SSH Telemetry</span>
          </div>

          <div class="meter-group">
            <div class="meter-label">
              <span>CPU Load Average (1m)</span>
              <strong>${r.cpu_load_1m !== null ? r.cpu_load_1m : '—'}</strong>
            </div>
          </div>

          <div class="meter-group">
            <div class="meter-label">
              <span>Memory Usage (${r.memory_used_mb || 0}MB / ${r.memory_total_mb || 0}MB)</span>
              <strong>${memPct}%</strong>
            </div>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill ${memClass}" style="width: ${Math.min(memPct, 100)}%"></div>
            </div>
          </div>

          ${diskBars}

          ${systemdBadges ? `<div style="margin-top: 14px;"><div class="meter-label"><span>Systemd Services</span></div>${systemdBadges}</div>` : ''}

          <!-- Process Breakdown Component -->
          <div class="proc-breakdown-section">
            <div class="proc-breakdown-header">
              <span class="proc-breakdown-title">
                <span>⚡</span> Resource Usage Breakdown
              </span>
              <div class="proc-segmented-toggle">
                <button type="button" class="proc-segmented-btn ${currentProcTab === 'cpu' ? 'active' : ''}" onclick="toggleCardProcessTab('${escapeHtml(r.device_id)}', 'cpu')">
                  🔥 CPU
                </button>
                <button type="button" class="proc-segmented-btn ${currentProcTab === 'mem' ? 'active' : ''}" onclick="toggleCardProcessTab('${escapeHtml(r.device_id)}', 'mem')">
                  💾 RAM
                </button>
              </div>
            </div>

            ${procsHtml}

            <button type="button" class="btn btn-secondary btn-sm" style="width: 100%; display: flex; align-items: center; justify-content: center; gap: 6px; font-weight: 500; font-size: 11.5px; margin-top: 4px;" onclick="openProcessModal('${escapeHtml(r.device_id)}')">
              <span>🔍</span> View Full Process Breakdown
            </button>
          </div>
        </div>
      `;
    }).join('');
  }

  function toggleCardProcessTab(deviceId, mode) {
    cardProcessTabs[deviceId] = mode;
    renderResourceCards();
  }
  window.toggleCardProcessTab = toggleCardProcessTab;

  function openProcessModal(deviceId) {
    modalProcessState.deviceId = deviceId;
    modalProcessState.tab = 'cpu';
    modalProcessState.filter = '';
    if (inputFilterProcesses) inputFilterProcesses.value = '';

    if (processModal) {
      processModal.classList.add('open');
      renderModalProcesses();
    }
  }
  window.openProcessModal = openProcessModal;

  function closeProcessModal() {
    if (processModal) {
      processModal.classList.remove('open');
    }
    modalProcessState.deviceId = null;
  }

  function renderModalProcesses() {
    if (!modalProcessState.deviceId) return;
    const r = cachedResources.find(item => item.device_id === modalProcessState.deviceId);
    if (!r) return;

    if (processModalTitle) {
      processModalTitle.textContent = `${r.device_name} (${r.device_ip}) - Process Breakdown`;
    }
    if (processModalSubtitle) {
      processModalSubtitle.textContent = `Inspect processes consuming RAM and CPU on ${r.device_name}`;
    }
    if (processModalCpuLoad) {
      processModalCpuLoad.textContent = r.cpu_load_1m !== null ? `${r.cpu_load_1m}` : '—';
    }
    if (processModalMemStats) {
      processModalMemStats.textContent = `${r.memory_used_mb || 0} MB / ${r.memory_total_mb || 0} MB (${r.memory_percent || 0}%)`;
    }

    if (btnTabProcsCpu) {
      btnTabProcsCpu.classList.toggle('active', modalProcessState.tab === 'cpu');
    }
    if (btnTabProcsMem) {
      btnTabProcsMem.classList.toggle('active', modalProcessState.tab === 'mem');
    }

    const allProcs = (modalProcessState.tab === 'cpu' ? r.top_cpu_processes : r.top_mem_processes) || [];
    const query = (modalProcessState.filter || '').trim().toLowerCase();

    const filtered = allProcs.filter(p => {
      if (!query) return true;
      const cmd = (p.command || '').toLowerCase();
      const args = (p.args || '').toLowerCase();
      const user = (p.user || '').toLowerCase();
      const pidStr = String(p.pid || '');
      return cmd.includes(query) || args.includes(query) || user.includes(query) || pidStr.includes(query);
    });

    if (!tbodyModalProcesses) return;

    if (filtered.length === 0) {
      tbodyModalProcesses.innerHTML = `<tr><td colspan="5" class="text-center text-muted" style="padding: 24px;">No processes found matching "${escapeHtml(query)}"</td></tr>`;
      return;
    }

    tbodyModalProcesses.innerHTML = filtered.map(p => {
      const cpuVal = typeof p.cpu_percent === 'number' ? p.cpu_percent : 0;
      const memVal = typeof p.mem_percent === 'number' ? p.mem_percent : 0;

      const cpuBarClass = cpuVal > 50 ? 'crit' : cpuVal > 20 ? 'warn' : 'normal';
      const memBarClass = memVal > 50 ? 'crit' : memVal > 20 ? 'warn' : 'normal';

      const showArgs = p.args && p.args !== p.command;

      return `
        <tr>
          <td><code style="font-size: 11.5px; font-weight: 600;">${p.pid}</code></td>
          <td><span class="badge" style="background: var(--border-subtle); color: var(--text-color); font-size: 11px;">${escapeHtml(p.user)}</span></td>
          <td>
            <div style="display: flex; align-items: center; gap: 6px;">
              <div class="progress-bar-bg" style="width: 40px; height: 6px; flex-shrink: 0;">
                <div class="progress-bar-fill ${cpuBarClass}" style="width: ${Math.min(cpuVal, 100)}%"></div>
              </div>
              <strong style="font-size: 12px; font-family: monospace;">${cpuVal}%</strong>
            </div>
          </td>
          <td>
            <div style="display: flex; align-items: center; gap: 6px;">
              <div class="progress-bar-bg" style="width: 40px; height: 6px; flex-shrink: 0;">
                <div class="progress-bar-fill ${memBarClass}" style="width: ${Math.min(memVal, 100)}%"></div>
              </div>
              <strong style="font-size: 12px; font-family: monospace;">${memVal}%</strong>
            </div>
          </td>
          <td>
            <div style="font-weight: 600; font-size: 12.5px; margin-bottom: 2px;">${escapeHtml(p.command)}</div>
            ${showArgs ? `<div class="proc-cmd-code" style="margin-top: 3px;">${escapeHtml(p.args)}</div>` : ''}
          </td>
        </tr>
      `;
    }).join('');
  }

  async function refreshProcessesLive() {
    if (!modalProcessState.deviceId) return;
    const devId = modalProcessState.deviceId;
    const r = cachedResources.find(item => item.device_id === devId);
    const devName = r ? r.device_name : devId;

    if (btnRefreshProcessesLive) btnRefreshProcessesLive.disabled = true;
    if (processModalRefreshIcon) processModalRefreshIcon.style.animation = 'spin 1s linear infinite';

    try {
      const res = await fetch(`/api/resources/${encodeURIComponent(devId)}/processes`, { method: 'POST' });
      const data = await res.json();
      if (!data.success) {
        showToast(`Failed to refresh processes: ${data.error || 'Unknown error'}`);
        return;
      }

      // Update cached entry
      if (r) {
        if (data.top_cpu_processes) r.top_cpu_processes = data.top_cpu_processes;
        if (data.top_mem_processes) r.top_mem_processes = data.top_mem_processes;
        if (data.cpu_load_1m !== undefined) r.cpu_load_1m = data.cpu_load_1m;
        if (data.memory_percent !== undefined) r.memory_percent = data.memory_percent;
        if (data.memory_used_mb !== undefined) r.memory_used_mb = data.memory_used_mb;
        if (data.memory_total_mb !== undefined) r.memory_total_mb = data.memory_total_mb;
      }

      renderModalProcesses();
      renderResourceCards();
      showToast(`Updated live process telemetry for ${devName}`);
    } catch (e) {
      console.error('Error refreshing processes:', e);
      showToast(`Error refreshing processes: ${e.message}`);
    } finally {
      if (btnRefreshProcessesLive) btnRefreshProcessesLive.disabled = false;
      if (processModalRefreshIcon) processModalRefreshIcon.style.animation = '';
    }
  }

  // Event Listeners for Process Modal
  if (btnCloseProcessModal) {
    btnCloseProcessModal.addEventListener('click', closeProcessModal);
  }
  if (btnCloseProcessModalBottom) {
    btnCloseProcessModalBottom.addEventListener('click', closeProcessModal);
  }
  if (processModal) {
    processModal.addEventListener('click', (e) => {
      if (e.target === processModal) closeProcessModal();
    });
  }
  if (btnTabProcsCpu) {
    btnTabProcsCpu.addEventListener('click', () => {
      modalProcessState.tab = 'cpu';
      renderModalProcesses();
    });
  }
  if (btnTabProcsMem) {
    btnTabProcsMem.addEventListener('click', () => {
      modalProcessState.tab = 'mem';
      renderModalProcesses();
    });
  }
  if (inputFilterProcesses) {
    inputFilterProcesses.addEventListener('input', (e) => {
      modalProcessState.filter = e.target.value;
      renderModalProcesses();
    });
  }
  if (btnRefreshProcessesLive) {
    btnRefreshProcessesLive.addEventListener('click', refreshProcessesLive);
  }
  if (btnRefreshResources) {
    btnRefreshResources.addEventListener('click', () => {
      loadResources();
      showToast('Refreshing system resources telemetry...');
    });
  }

  function formatNotifyMode(mode) {
    switch (mode) {
      case 'immediate': return 'Immediate';
      case 'batched': return 'Batched Digest';
      case 'on_change': return 'On State Change';
      case 'periodic': return 'Periodic';
      case 'never': return 'Silent / Never';
      default: return mode ? mode.replace(/_/g, ' ') : 'Standard';
    }
  }

  // Feature categories and metadata are defined near the top of the file before routeHierarchy


  async function loadTelegramConfig() {
    try {
      const res = await fetch('/api/telegram');
      const data = await res.json();
      if (!data.success) return;

      const tokenInput = document.getElementById('tg-input-token');
      const chatIdInput = document.getElementById('tg-input-chatid');
      const parseModeSelect = document.getElementById('tg-select-parse-mode');
      const enabledToggle = document.getElementById('tg-toggle-enabled');
      const liveBadge = document.getElementById('tg-live-badge');
      const pauseBanner = document.getElementById('tg-pause-banner');
      const pauseCountdown = document.getElementById('tg-pause-countdown');
      const btnResume = document.getElementById('btn-tg-resume');

      if (tokenInput && !tokenInput.value) tokenInput.value = data.bot_token || '';
      if (chatIdInput && !chatIdInput.value) chatIdInput.value = data.chat_id || '';
      if (parseModeSelect) parseModeSelect.value = data.parse_mode || 'HTML';
      if (enabledToggle) enabledToggle.checked = data.enabled !== false;

      if (!data.enabled) {
        liveBadge.textContent = '🔴 Disabled';
        liveBadge.className = 'badge badge-danger';
        if (btnResume) btnResume.style.display = 'none';
        if (pauseBanner) pauseBanner.style.display = 'none';
      } else if (data.is_paused) {
        const mins = Math.ceil((data.pause_remaining_seconds || 0) / 60);
        liveBadge.textContent = `⏸️ Paused (${mins}m)`;
        liveBadge.className = 'badge badge-warning';
        if (btnResume) btnResume.style.display = 'inline-block';
        if (pauseBanner) {
          pauseBanner.style.display = 'block';
          pauseCountdown.textContent = `${mins} minute${mins !== 1 ? 's' : ''}`;
        }
      } else {
        liveBadge.textContent = '🟢 Active';
        liveBadge.className = 'badge badge-success';
        if (btnResume) btnResume.style.display = 'none';
        if (pauseBanner) pauseBanner.style.display = 'none';
      }
    } catch (e) {
      console.error('Failed to load Telegram config:', e);
    }
  }

  function matchesFeatureSearch(fname, fcfg, info, catInfo, query) {
    if (!query) return true;
    const q = query.toLowerCase().trim();
    if (fname.toLowerCase().includes(q)) return true;
    if ((info.title || '').toLowerCase().includes(q)) return true;
    if ((info.desc || '').toLowerCase().includes(q)) return true;
    if ((catInfo.name || '').toLowerCase().includes(q)) return true;
    if ((info.suboptions || []).some(o => (o.label || '').toLowerCase().includes(q) || (o.key || '').toLowerCase().includes(q))) return true;
    return false;
  }

  function renderFeatureCard(fname, fcfg, catKey, catInfo) {
    const info = featureMeta[fname] || {
      title: fname.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      icon: '⚙️',
      desc: 'Background monitoring feature',
      suboptions: [],
      category: 'other'
    };

    const hasSubopts = info.suboptions && info.suboptions.length > 0;
    const suboptPill = hasSubopts
      ? `<span class="pill-tag" style="background: rgba(88, 166, 255, 0.1); border-color: rgba(88, 166, 255, 0.3); color: var(--primary);">⚙️ ${info.suboptions.length} sub-controls</span>`
      : '<span class="pill-tag text-muted">⚙️ Standard triggers</span>';

    return `
      <div class="feature-card feature-row" data-feature="${escapeHtml(fname)}" data-category="${escapeHtml(catKey)}">
        <div class="feature-card-header">
          <div class="feature-card-info" data-feature="${escapeHtml(fname)}" title="Click to configure feature in popup">
            <span class="feature-icon-badge">${info.icon}</span>
            <div>
              <h4 class="feature-title">${escapeHtml(info.title)}</h4>
              <span class="badge feature-status-badge ${fcfg.enabled ? 'badge-success' : 'badge-muted'}" style="margin-top: 4px;">
                ${fcfg.enabled ? '● Active' : '○ Inactive'}
              </span>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 6px;">
            <label class="switch" style="margin-bottom: 0;">
              <input type="checkbox" class="feature-enabled-toggle" ${fcfg.enabled ? 'checked' : ''} data-feature="${escapeHtml(fname)}" id="toggle-${fname}">
              <span class="slider round"></span>
            </label>
          </div>
        </div>

        <p class="feature-card-desc">
          ${escapeHtml(info.desc)}
        </p>

        <div class="feature-meta-pills">
          <span class="pill-tag">⏱️ ${fcfg.interval_seconds}s</span>
          <span class="pill-tag">🔔 ${formatNotifyMode(fcfg.notify_mode)}</span>
          ${suboptPill}
        </div>

        <div class="feature-card-footer">
          <span style="font-size: 11px; color: var(--text-muted); font-weight: 500;">
            ${escapeHtml(catInfo.name)}
          </span>
          <button type="button" class="btn btn-secondary btn-sm btn-configure-feature" data-feature="${escapeHtml(fname)}" title="Configure feature settings and sub-feature controls in popup">
            ⚙️ Configure${hasSubopts ? ' Sub-Features' : ''}
          </button>
        </div>
      </div>
    `;
  }

  function renderFeaturesList() {
    const list = document.getElementById('features-config-list');
    if (!list) return;

    const allEntries = Object.entries(allFeatures);

    // Compute category counts and active/inactive counts across all features
    const categoryCounts = {};
    let totalCount = 0;
    let activeCount = 0;
    let inactiveCount = 0;

    allEntries.forEach(([fname, fcfg]) => {
      totalCount++;
      if (fcfg.enabled !== false) activeCount++;
      else inactiveCount++;

      const info = featureMeta[fname] || {};
      const catKey = info.category || 'other';
      categoryCounts[catKey] = (categoryCounts[catKey] || 0) + 1;
    });

    // Update Summary Stats Badge
    if (featuresSummaryStats) {
      featuresSummaryStats.textContent = `${activeCount} Active · ${inactiveCount} Inactive`;
      featuresSummaryStats.className = activeCount > 0 ? 'badge badge-primary' : 'badge badge-muted';
    }

    // Render Filter Chips
    if (featuresFilterChips) {
      const chips = [
        `<button type="button" class="filter-chip ${currentFeatureFilter === 'all' ? 'active' : ''}" data-filter="all">All <span class="chip-count">${totalCount}</span></button>`,
        `<button type="button" class="filter-chip ${currentFeatureFilter === 'active' ? 'active' : ''}" data-filter="active">🟢 Active <span class="chip-count">${activeCount}</span></button>`,
        `<button type="button" class="filter-chip ${currentFeatureFilter === 'inactive' ? 'active' : ''}" data-filter="inactive">⚪ Inactive <span class="chip-count">${inactiveCount}</span></button>`,
        ...Object.entries(featureCategories).map(([ckey, cinfo]) => {
          const count = categoryCounts[ckey] || 0;
          if (count === 0) return '';
          return `<button type="button" class="filter-chip ${currentFeatureFilter === ckey ? 'active' : ''}" data-filter="${escapeHtml(ckey)}">${cinfo.icon} ${escapeHtml(cinfo.name)} <span class="chip-count">${count}</span></button>`;
        })
      ];
      featuresFilterChips.innerHTML = chips.filter(Boolean).join('');

      // Wire up chip click handlers
      featuresFilterChips.querySelectorAll('.filter-chip').forEach(btn => {
        btn.addEventListener('click', () => {
          currentFeatureFilter = btn.getAttribute('data-filter');
          renderFeaturesList();
        });
      });
    }

    // Group features by Category
    const categoriesToRender = { ...featureCategories };
    allEntries.forEach(([fname]) => {
      const cat = (featureMeta[fname] && featureMeta[fname].category) || 'other';
      if (!categoriesToRender[cat]) {
        categoriesToRender[cat] = {
          name: 'Additional Features',
          icon: '⚙️',
          desc: 'Custom monitoring plugins and features'
        };
      }
    });

    let renderedGroupsHtml = '';
    let totalMatchingFeatures = 0;

    Object.entries(categoriesToRender).forEach(([catKey, catInfo]) => {
      // Find matching features for this category
      const matchingInCat = allEntries.filter(([fname, fcfg]) => {
        const info = featureMeta[fname] || {};
        const fCat = info.category || 'other';
        if (fCat !== catKey) return false;

        // Check active / inactive / category filter
        if (currentFeatureFilter === 'active' && fcfg.enabled === false) return false;
        if (currentFeatureFilter === 'inactive' && fcfg.enabled !== false) return false;
        if (currentFeatureFilter !== 'all' && currentFeatureFilter !== 'active' && currentFeatureFilter !== 'inactive' && currentFeatureFilter !== catKey) return false;

        // Check search query
        return matchesFeatureSearch(fname, fcfg, info, catInfo, featureSearchQuery);
      });

      if (matchingInCat.length > 0) {
        totalMatchingFeatures += matchingInCat.length;
        const cardsHtml = matchingInCat.map(([fname, fcfg]) => renderFeatureCard(fname, fcfg, catKey, catInfo)).join('');

        renderedGroupsHtml += `
          <div class="feature-category-group" data-category="${escapeHtml(catKey)}">
            <div class="feature-category-header">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 20px;">${catInfo.icon}</span>
                <div>
                  <h4 class="feature-category-title">${escapeHtml(catInfo.name)}</h4>
                  <span style="font-size: 11.5px; color: var(--text-muted);">${escapeHtml(catInfo.desc)}</span>
                </div>
              </div>
              <span class="pill-tag">${matchingInCat.length} feature${matchingInCat.length > 1 ? 's' : ''}</span>
            </div>
            <div class="features-grid">
              ${cardsHtml}
            </div>
          </div>
        `;
      }
    });

    if (totalMatchingFeatures === 0) {
      list.innerHTML = `
        <div style="text-align: center; padding: 40px 20px; color: var(--text-muted); background: var(--border-subtle); border: 1px dashed var(--border-color); border-radius: var(--radius-sm);">
          <span style="font-size: 32px; display: block; margin-bottom: 8px;">🔍</span>
          <h4 style="margin: 0 0 6px 0; font-size: 14.5px; color: var(--text-main);">No matching monitoring features</h4>
          <p style="font-size: 12px; margin: 0 0 16px 0;">No features match your current search query or filter selection.</p>
          <button type="button" class="btn btn-secondary btn-sm" id="btn-reset-features-search">Reset Filters</button>
        </div>
      `;

      const btnReset = document.getElementById('btn-reset-features-search');
      if (btnReset) {
        btnReset.addEventListener('click', () => {
          currentFeatureFilter = 'all';
          featureSearchQuery = '';
          if (featuresSearchInput) featuresSearchInput.value = '';
          renderFeaturesList();
        });
      }
      return;
    }

    list.innerHTML = renderedGroupsHtml;

    // Attach Configure button click handlers
    list.querySelectorAll('.btn-configure-feature').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const fname = btn.getAttribute('data-feature');
        openFeatureModal(fname);
      });
    });

    // Attach card info click handlers
    list.querySelectorAll('.feature-card-info').forEach(infoEl => {
      infoEl.addEventListener('click', () => {
        const fname = infoEl.getAttribute('data-feature');
        openFeatureModal(fname);
      });
    });

    // Attach quick toggle switch handlers
    list.querySelectorAll('.feature-enabled-toggle').forEach(chk => {
      chk.addEventListener('change', async (e) => {
        e.stopPropagation();
        const fname = chk.getAttribute('data-feature');
        const isChecked = chk.checked;

        const card = chk.closest('.feature-card');
        const statusBadge = card ? card.querySelector('.feature-status-badge') : null;
        if (statusBadge) {
          statusBadge.textContent = isChecked ? '● Active' : '○ Inactive';
          statusBadge.className = `badge feature-status-badge ${isChecked ? 'badge-success' : 'badge-muted'}`;
        }

        try {
          const res = await fetch('/api/features', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              [fname]: { enabled: isChecked }
            })
          });
          const data = await res.json();
          if (data.success) {
            const title = featureMeta[fname]?.title || fname;
            showToast(`✓ ${title} ${isChecked ? 'activated' : 'disabled'}`);
            if (allFeatures[fname]) {
              allFeatures[fname].enabled = isChecked;
            }
            renderFeaturesList();
          } else {
            showToast(`Error: ${data.error}`);
            chk.checked = !isChecked;
            if (statusBadge) {
              statusBadge.textContent = !isChecked ? '● Active' : '○ Inactive';
              statusBadge.className = `badge feature-status-badge ${!isChecked ? 'badge-success' : 'badge-muted'}`;
            }
          }
        } catch (err) {
          showToast(`Toggle failed: ${err}`);
          chk.checked = !isChecked;
          if (statusBadge) {
            statusBadge.textContent = !isChecked ? '● Active' : '○ Inactive';
            statusBadge.className = `badge feature-status-badge ${!isChecked ? 'badge-success' : 'badge-muted'}`;
          }
        }
      });
    });
  }

  async function loadFeatures() {
    try {
      const res = await fetch('/api/features');
      const data = await res.json();
      if (!data.success) return;
      allFeatures = data.features;
      renderFeaturesList();
      renderDashboardFeatureTiles();
    } catch (e) {
      console.error('Failed to load features:', e);
    }
  }

  if (featuresSearchInput) {
    featuresSearchInput.addEventListener('input', () => {
      featureSearchQuery = featuresSearchInput.value.toLowerCase().trim();
      renderFeaturesList();
    });
  }

  // Feature Configuration Modal Logic
  function updateFeatureModeVisibility() {
    if (formFeatBatchGroup && formFeatMode) {
      formFeatBatchGroup.style.display = formFeatMode.value === 'batched' ? 'block' : 'none';
    }
  }

  if (formFeatMode) {
    formFeatMode.addEventListener('change', updateFeatureModeVisibility);
  }

  if (formFeatEnabled) {
    formFeatEnabled.addEventListener('change', () => {
      if (formFeatEnabledLabel) {
        formFeatEnabledLabel.textContent = formFeatEnabled.checked ? 'Active' : 'Disabled';
      }
    });
  }

  // --- Flag Half-Staff Monitor Modal Customization ---
  let currentFlagSources = [];

  function getFlagSourcesFromConfig(fcfg) {
    let sources = fcfg?.options?.sources;
    if (typeof sources === 'string') {
      try {
        sources = JSON.parse(sources);
      } catch (e) {
        sources = null;
      }
    }
    if (!Array.isArray(sources) || sources.length === 0) {
      sources = [
        {
          id: 'school_shootings_2020s',
          name: 'US School Shootings (2020s)',
          url: 'https://en.wikipedia.org/wiki/List_of_school_shootings_in_the_United_States_(2020s)',
          enabled: true
        },
        {
          id: 'school_shootings_2000s',
          name: 'US School Shootings (2000–present)',
          url: 'https://en.wikipedia.org/wiki/List_of_school_shootings_in_the_United_States_(2000%E2%80%93present)',
          enabled: true
        }
      ];
    }
    return JSON.parse(JSON.stringify(sources));
  }

  function renderFlagSourcesTableRows() {
    if (!currentFlagSources || currentFlagSources.length === 0) {
      return `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 12px;">No Wikipedia sources configured. Add one below.</td></tr>`;
    }
    return currentFlagSources.map((src, idx) => `
      <tr data-src-idx="${idx}">
        <td style="width: 45px; text-align: center;">
          <input type="checkbox" class="flag-src-toggle" data-idx="${idx}" ${src.enabled !== false ? 'checked' : ''} title="Toggle active source">
        </td>
        <td style="font-weight: 500; font-size: 12px;">${escapeHtml(src.name || 'Untitled Source')}</td>
        <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
          <a href="${escapeHtml(src.url)}" target="_blank" rel="noopener" style="color: var(--primary); font-size: 11px;">${escapeHtml(src.url)} ↗</a>
        </td>
        <td style="white-space: nowrap; text-align: right;">
          <button type="button" class="btn btn-secondary btn-xs btn-test-src" data-idx="${idx}" title="Test scraping this Wikipedia page">⚡ Test</button>
          <button type="button" class="btn btn-secondary btn-xs btn-del-src" data-idx="${idx}" style="margin-left: 4px; color: var(--danger);" title="Remove this source">✕</button>
        </td>
      </tr>
    `).join('');
  }

  function attachFlagSourceRowListeners() {
    if (!featureModalSuboptions) return;

    featureModalSuboptions.querySelectorAll('.flag-src-toggle').forEach(chk => {
      chk.addEventListener('change', () => {
        const idx = parseInt(chk.getAttribute('data-idx'), 10);
        if (currentFlagSources[idx]) {
          currentFlagSources[idx].enabled = chk.checked;
        }
      });
    });

    featureModalSuboptions.querySelectorAll('.btn-del-src').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const idx = parseInt(btn.getAttribute('data-idx'), 10);
        if (currentFlagSources[idx]) {
          const removed = currentFlagSources.splice(idx, 1);
          showToast(`Removed source: ${removed[0]?.name || 'Article'}`);
          const tbody = document.getElementById('flag-sources-tbody');
          if (tbody) {
            tbody.innerHTML = renderFlagSourcesTableRows();
            attachFlagSourceRowListeners();
          }
        }
      });
    });

    featureModalSuboptions.querySelectorAll('.btn-test-src').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.preventDefault();
        const idx = parseInt(btn.getAttribute('data-idx'), 10);
        const src = currentFlagSources[idx];
        if (!src) return;

        btn.disabled = true;
        btn.textContent = 'Testing...';
        try {
          const res = await fetch('/api/flag/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: src.url })
          });
          const data = await res.json();
          if (data.success) {
            showToast(`✓ Found ${data.tables_found} table(s), parsed ${data.total_incidents_parsed} incident(s)`);
            displayProbeResults(data);
          } else {
            showToast(`Probe error: ${data.error || 'Failed to parse page'}`);
          }
        } catch (err) {
          showToast(`Test error: ${err}`);
        } finally {
          btn.disabled = false;
          btn.textContent = '⚡ Test';
        }
      });
    });
  }

  function displayProbeResults(data) {
    const probeBox = document.getElementById('flag-probe-results');
    if (!probeBox) return;

    if (!data.success) {
      probeBox.style.display = 'block';
      probeBox.innerHTML = `
        <div style="padding: 10px 14px; background: rgba(248, 81, 73, 0.1); border: 1px solid rgba(248, 81, 73, 0.3); border-radius: var(--radius-sm); color: var(--danger); font-size: 12px;">
          ❌ <strong>Probe Failed:</strong> ${escapeHtml(data.error || 'Unknown error')}
        </div>
      `;
      return;
    }

    const samples = data.sample_incidents || [];
    probeBox.style.display = 'block';
    probeBox.innerHTML = `
      <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 12px; margin-top: 10px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <div>
            <strong style="font-size: 12px; color: var(--success);">✓ Inspection Succeeded</strong>
            <span style="font-size: 11px; color: var(--text-muted); display: block;">
              Found <strong>${data.tables_found}</strong> wikitable(s) &bull; Extracted <strong>${data.total_incidents_parsed}</strong> total incidents
            </span>
          </div>
          <button type="button" class="btn btn-primary btn-xs" id="btn-add-probed-source" data-url="${escapeHtml(data.url)}">
            + Add to Sources
          </button>
        </div>
        ${samples.length > 0 ? `
          <div style="max-height: 180px; overflow-y: auto; overflow-x: auto; border: 1px solid var(--border-color); border-radius: 4px;">
            <table class="data-table" style="font-size: 11px; width: 100%; margin: 0;">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Location</th>
                  <th>Dead</th>
                  <th>Injured</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                ${samples.slice(0, 5).map(s => `
                  <tr>
                    <td style="white-space: nowrap;">${escapeHtml(s.date)}</td>
                    <td>${escapeHtml(s.location)}</td>
                    <td style="color: ${s.dead > 0 ? 'var(--danger)' : 'inherit'}; font-weight: 600;">${s.dead}</td>
                    <td>${s.injured}</td>
                    <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(s.desc || '')}">
                      ${escapeHtml(s.desc || '—')}
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        ` : '<div style="font-size: 11px; color: var(--text-muted); font-style: italic;">No rows parsed from wikitables on this page.</div>'}
      </div>
    `;

    const btnAddProbed = document.getElementById('btn-add-probed-source');
    if (btnAddProbed) {
      btnAddProbed.addEventListener('click', () => {
        const url = btnAddProbed.getAttribute('data-url');
        if (!url) return;
        const titleMatch = url.match(/\/wiki\/(.+)$/);
        const autoTitle = titleMatch ? decodeURIComponent(titleMatch[1]).replace(/_/g, ' ') : 'Wikipedia Article';
        currentFlagSources.push({
          id: 'src_' + Date.now(),
          name: autoTitle,
          url: url,
          enabled: true
        });
        showToast(`✓ Added source: ${autoTitle}`);
        const tbody = document.getElementById('flag-sources-tbody');
        if (tbody) {
          tbody.innerHTML = renderFlagSourcesTableRows();
          attachFlagSourceRowListeners();
        }
        probeBox.style.display = 'none';
      });
    }
  }

  function renderFlagMonitorModal(fcfg) {
    currentFlagSources = getFlagSourcesFromConfig(fcfg);
    const opts = fcfg.options || {};
    const durationDays = opts.duration_days !== undefined ? opts.duration_days : 4;
    const minDeaths = opts.min_deaths !== undefined ? opts.min_deaths : 1;
    const minCasualties = opts.min_casualties !== undefined ? opts.min_casualties : 1;
    const stateFilter = opts.state_filter !== undefined ? opts.state_filter : '';

    if (formFeatSuboptionsCount) {
      formFeatSuboptionsCount.textContent = `${currentFlagSources.length} Articles & Rules`;
    }

    if (!featureModalSuboptions) return;

    featureModalSuboptions.innerHTML = `
      <!-- Incident Rules & Thresholds -->
      <div style="background: var(--border-subtle); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 14px;">
        <h4 style="margin: 0 0 10px 0; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
          <span>🎯</span> Incident Thresholds & Half-Staff Duration
        </h4>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
          <div class="form-group" style="margin-bottom: 0;">
            <label for="modal-opt-duration_days" style="font-size: 12px; font-weight: 500;">Half-Staff Duration (Days)</label>
            <input type="number" id="modal-opt-duration_days" class="input" min="1" max="30" value="${escapeHtml(durationDays)}" style="width: 100%;">
            <span style="font-size: 10.5px; color: var(--text-muted); display: block; margin-top: 2px;">Days flag remains at half-staff</span>
          </div>
          <div class="form-group" style="margin-bottom: 0;">
            <label for="modal-opt-min_deaths" style="font-size: 12px; font-weight: 500;">Minimum Fatalities Threshold</label>
            <input type="number" id="modal-opt-min_deaths" class="input" min="0" max="100" value="${escapeHtml(minDeaths)}" style="width: 100%;">
            <span style="font-size: 10.5px; color: var(--text-muted); display: block; margin-top: 2px;">Minimum deaths required to trigger alert</span>
          </div>
          <div class="form-group" style="margin-bottom: 0;">
            <label for="modal-opt-min_casualties" style="font-size: 12px; font-weight: 500;">Minimum Total Casualties</label>
            <input type="number" id="modal-opt-min_casualties" class="input" min="0" max="100" value="${escapeHtml(minCasualties)}" style="width: 100%;">
            <span style="font-size: 10.5px; color: var(--text-muted); display: block; margin-top: 2px;">Dead + injured casualties threshold</span>
          </div>
          <div class="form-group" style="margin-bottom: 0;">
            <label for="modal-opt-state_filter" style="font-size: 12px; font-weight: 500;">State / Location Filter</label>
            <input type="text" id="modal-opt-state_filter" class="input" placeholder="e.g. FL, TX (leave blank for any)" value="${escapeHtml(stateFilter)}" style="width: 100%;">
            <span style="font-size: 10.5px; color: var(--text-muted); display: block; margin-top: 2px;">Filter incidents by comma-separated state codes</span>
          </div>
        </div>
      </div>

      <!-- Monitored Wikipedia Articles Table -->
      <div style="background: var(--border-subtle); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
          <div>
            <h4 style="margin: 0; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
              <span>📚</span> Monitored Wikipedia Articles
            </h4>
            <span style="font-size: 11px; color: var(--text-muted);">Pages scanned for tables with incident dates and casualty counts</span>
          </div>
          <button type="button" class="btn btn-secondary btn-xs" id="btn-flag-toggle-add-form">+ Add Source</button>
        </div>

        <!-- Add Source Form (Collapsible) -->
        <div id="flag-add-source-form" style="display: none; background: var(--bg-card); border: 1px dashed var(--border-color); border-radius: var(--radius-sm); padding: 12px; margin-bottom: 12px;">
          <h5 style="margin: 0 0 8px 0; font-size: 12px; font-weight: 600;">Add Wikipedia Article to Monitor</h5>
          <div style="display: grid; grid-template-columns: 1fr 2fr auto; gap: 8px; align-items: flex-end;">
            <div class="form-group" style="margin-bottom: 0;">
              <label for="flag-new-source-name" style="font-size: 11.5px;">Article Name</label>
              <input type="text" id="flag-new-source-name" class="input" placeholder="e.g. 2026 US Mass Shootings" style="width: 100%;">
            </div>
            <div class="form-group" style="margin-bottom: 0;">
              <label for="flag-new-source-url" style="font-size: 11.5px;">Wikipedia URL</label>
              <input type="url" id="flag-new-source-url" class="input" placeholder="https://en.wikipedia.org/wiki/..." style="width: 100%;">
            </div>
            <button type="button" class="btn btn-primary btn-sm" id="btn-flag-add-source-submit" style="height: 33px;">Add</button>
          </div>
        </div>

        <!-- Table of Sources -->
        <div style="border: 1px solid var(--border-color); border-radius: var(--radius-sm); overflow-x: auto; background: var(--bg-card);">
          <table class="data-table" style="font-size: 11.5px; width: 100%; margin: 0;">
            <thead>
              <tr>
                <th style="width: 45px; text-align: center;">Active</th>
                <th>Source Name</th>
                <th>Wikipedia URL</th>
                <th style="text-align: right;">Actions</th>
              </tr>
            </thead>
            <tbody id="flag-sources-tbody">
              ${renderFlagSourcesTableRows()}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Live Wikipedia URL Inspector & Testing Tool -->
      <div style="background: var(--border-subtle); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 14px;">
        <h4 style="margin: 0 0 6px 0; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
          <span>⚡</span> Live Wikipedia Table Inspector
        </h4>
        <p style="font-size: 11px; color: var(--text-muted); margin: 0 0 10px 0;">
          Test any Wikipedia URL to verify if tables and dates can be automatically detected before adding it to your monitor.
        </p>
        <div style="display: flex; gap: 8px; align-items: center;">
          <input type="url" id="flag-probe-url-input" class="input" placeholder="https://en.wikipedia.org/wiki/List_of_mass_shootings_in_the_United_States..." style="flex: 1;">
          <button type="button" class="btn btn-secondary btn-sm" id="btn-probe-wikipedia">⚡ Test & Parse</button>
        </div>
        <div id="flag-probe-results" style="display: none; margin-top: 8px;"></div>
      </div>

      <!-- Live Check Action -->
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: rgba(88, 166, 255, 0.08); border: 1px solid rgba(88, 166, 255, 0.25); border-radius: var(--radius-sm);">
        <div>
          <strong style="font-size: 12.5px; color: var(--text-main);">Instant Flag Check</strong>
          <span style="font-size: 11px; color: var(--text-muted); display: block;">Run all active Wikipedia queries right now</span>
        </div>
        <button type="button" class="btn btn-secondary btn-sm" id="btn-modal-flag-check">⚡ Execute Check</button>
      </div>
    `;

    attachFlagSourceRowListeners();

    // Toggle Add Source Form
    const btnToggleAdd = document.getElementById('btn-flag-toggle-add-form');
    const addForm = document.getElementById('flag-add-source-form');
    if (btnToggleAdd && addForm) {
      btnToggleAdd.addEventListener('click', () => {
        const isHidden = addForm.style.display === 'none';
        addForm.style.display = isHidden ? 'block' : 'none';
        btnToggleAdd.textContent = isHidden ? 'Hide Form' : '+ Add Source';
      });
    }

    // Submit Add Source
    const btnAddSubmit = document.getElementById('btn-flag-add-source-submit');
    const inputName = document.getElementById('flag-new-source-name');
    const inputUrl = document.getElementById('flag-new-source-url');
    if (btnAddSubmit && inputName && inputUrl) {
      btnAddSubmit.addEventListener('click', () => {
        const name = inputName.value.trim();
        const url = inputUrl.value.trim();
        if (!url) {
          showToast('Please enter a valid Wikipedia URL');
          return;
        }
        currentFlagSources.push({
          id: 'src_' + Date.now(),
          name: name || 'Wikipedia Source',
          url: url,
          enabled: true
        });
        showToast(`✓ Added source: ${name || url}`);
        inputName.value = '';
        inputUrl.value = '';
        addForm.style.display = 'none';
        if (btnToggleAdd) btnToggleAdd.textContent = '+ Add Source';
        const tbody = document.getElementById('flag-sources-tbody');
        if (tbody) {
          tbody.innerHTML = renderFlagSourcesTableRows();
          attachFlagSourceRowListeners();
        }
      });
    }

    // Live Probe button
    const btnProbe = document.getElementById('btn-probe-wikipedia');
    const probeInput = document.getElementById('flag-probe-url-input');
    if (btnProbe && probeInput) {
      btnProbe.addEventListener('click', async () => {
        const url = probeInput.value.trim();
        if (!url) {
          showToast('Please enter a Wikipedia URL to test');
          return;
        }
        btnProbe.disabled = true;
        btnProbe.textContent = 'Probing...';
        try {
          const res = await fetch('/api/flag/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
          });
          const data = await res.json();
          displayProbeResults(data);
        } catch (err) {
          showToast(`Probe failed: ${err}`);
        } finally {
          btnProbe.disabled = false;
          btnProbe.textContent = '⚡ Test & Parse';
        }
      });
    }

    // Modal Flag Check button
    const btnModalCheck = document.getElementById('btn-modal-flag-check');
    if (btnModalCheck) {
      btnModalCheck.addEventListener('click', async () => {
        btnModalCheck.disabled = true;
        btnModalCheck.textContent = 'Checking...';
        try {
          const res = await fetch('/api/flag/check', { method: 'POST' });
          const data = await res.json();
          if (data.success) {
            showToast('✓ Flag status updated from Wikipedia');
            await loadStatus();
          } else {
            showToast(`Flag check error: ${data.error}`);
          }
        } catch (err) {
          showToast(`Check failed: ${err}`);
        } finally {
          btnModalCheck.disabled = false;
          btnModalCheck.textContent = '⚡ Execute Check';
        }
      });
    }
  }

  function openFeatureModal(fname, updateRoute = true) {
    if (fname === 'speedtest') {
      openSpeedtestModal(updateRoute);
      return;
    }

    if (updateRoute) {
      navigateTo('features', fname, true);
      return;
    }

    const fcfg = allFeatures[fname];
    if (!fcfg) return;

    const info = featureMeta[fname] || {
      title: fname.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      icon: '⚙️',
      desc: 'Background monitoring feature',
      suboptions: []
    };

    if (formFeatName) formFeatName.value = fname;
    if (featureModalIcon) featureModalIcon.textContent = info.icon || '⚙️';
    if (featureModalTitle) featureModalTitle.textContent = `${info.title} Configuration`;
    if (featureModalDesc) featureModalDesc.textContent = info.desc;

    if (formFeatEnabled) {
      formFeatEnabled.checked = fcfg.enabled !== false;
      if (formFeatEnabledLabel) {
        formFeatEnabledLabel.textContent = formFeatEnabled.checked ? 'Active' : 'Disabled';
      }
    }
    if (formFeatInterval) formFeatInterval.value = fcfg.interval_seconds || 300;
    if (formFeatMode) formFeatMode.value = fcfg.notify_mode || 'on_change';
    if (formFeatBatchInterval) formFeatBatchInterval.value = fcfg.batch_interval_seconds || 300;

    updateFeatureModeVisibility();

    if (fname === 'flag_status') {
      renderFlagMonitorModal(fcfg);
      if (featureModal) featureModal.classList.add('open');
      return;
    }

    const opts = fcfg.options || {};
    const subopts = info.suboptions || [];
    const knownKeys = new Set(subopts.map(o => o.key));
    const extraOpts = Object.entries(opts)
      .filter(([k]) => !knownKeys.has(k) && !['enabled', 'interval_seconds', 'notify_mode', 'batch_interval_seconds', 'name', 'token', 'chatid', 'bot_token', 'chat_id'].includes(k.toLowerCase()))
      .map(([k, v]) => ({
        key: k,
        label: k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        type: typeof v === 'boolean' ? 'checkbox' : (typeof v === 'number' ? 'number' : 'text'),
        default: v
      }));

    const allSuboptsToRender = [...subopts, ...extraOpts];

    if (formFeatSuboptionsCount) {
      formFeatSuboptionsCount.textContent = allSuboptsToRender.length > 0 
        ? `${allSuboptsToRender.length} parameter${allSuboptsToRender.length > 1 ? 's' : ''}`
        : 'Standard Triggers';
    }

    if (featureModalSuboptions) {
      if (allSuboptsToRender.length === 0) {
        featureModalSuboptions.innerHTML = `
          <div style="padding: 16px; background: var(--border-subtle); border: 1px dashed var(--border-color); border-radius: var(--radius-sm); color: var(--text-muted); font-size: 12.5px; text-align: center;">
            ℹ️ This feature operates with standard check interval and notification triggers. No additional sub-feature parameters are required.
          </div>
        `;
      } else {
        featureModalSuboptions.innerHTML = allSuboptsToRender.map(opt => {
          const currVal = opts[opt.key] !== undefined ? opts[opt.key] : opt.default;

          if (opt.type === 'checkbox') {
            const isChecked = currVal === true || String(currVal).toLowerCase() === 'true';
            return `
              <div class="sub-opt-item" style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--border-subtle); border: 1px solid var(--border-color); border-radius: var(--radius-sm);">
                <div style="flex: 1; padding-right: 12px;">
                  <label for="modal-opt-${escapeHtml(opt.key)}" style="font-size: 13px; font-weight: 500; cursor: pointer; margin-bottom: 0; color: var(--text-main); display: block;">${escapeHtml(opt.label)}</label>
                  <code style="font-size: 10.5px; color: var(--text-muted);">${escapeHtml(opt.key)}</code>
                </div>
                <label class="switch" style="flex-shrink: 0; margin-bottom: 0;">
                  <input type="checkbox" class="modal-sub-opt-input" data-opt-key="${escapeHtml(opt.key)}" id="modal-opt-${escapeHtml(opt.key)}" ${isChecked ? 'checked' : ''}>
                  <span class="slider round"></span>
                </label>
              </div>
            `;
          } else {
            return `
              <div class="sub-opt-item form-group" style="margin-bottom: 0; padding: 10px 14px; background: var(--border-subtle); border: 1px solid var(--border-color); border-radius: var(--radius-sm);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                  <label for="modal-opt-${escapeHtml(opt.key)}" style="font-size: 12.5px; font-weight: 500; margin-bottom: 0; color: var(--text-main);">${escapeHtml(opt.label)}</label>
                  <code style="font-size: 10.5px; color: var(--text-muted);">${escapeHtml(opt.key)}</code>
                </div>
                <input type="${opt.type}" step="${opt.type === 'number' ? 'any' : ''}" class="input modal-sub-opt-input" data-opt-key="${escapeHtml(opt.key)}" id="modal-opt-${escapeHtml(opt.key)}" value="${escapeHtml(currVal !== undefined && currVal !== null ? currVal : '')}" style="width: 100%;">
              </div>
            `;
          }
        }).join('');
      }
    }

    if (featureModal) featureModal.classList.add('open');
  }

  function closeFeatureModal() {
    if (featureModal) featureModal.classList.remove('open');
    if (window.location.hash.startsWith('#features/') || window.location.hash.includes('feature=')) {
      navigateTo('features', null, true);
    } else {
      updateBreadcrumbs(currentTab, null);
    }
  }

  if (btnCloseFeatureModal) {
    btnCloseFeatureModal.addEventListener('click', closeFeatureModal);
  }

  if (btnCancelFeatureModal) {
    btnCancelFeatureModal.addEventListener('click', closeFeatureModal);
  }

  if (featureModal) {
    featureModal.addEventListener('click', (e) => {
      if (e.target === featureModal) closeFeatureModal();
    });
  }

  if (btnReloadFeatures) {
    btnReloadFeatures.addEventListener('click', async () => {
      btnReloadFeatures.disabled = true;
      await loadFeatures();
      showToast('Features refreshed');
      btnReloadFeatures.disabled = false;
    });
  }

  if (featureForm) {
    featureForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fname = formFeatName.value;
      if (!fname) return;

      const enabled = formFeatEnabled.checked;
      const interval_seconds = parseInt(formFeatInterval.value, 10) || 300;
      const notify_mode = formFeatMode.value;
      const batch_interval_seconds = parseInt(formFeatBatchInterval.value, 10) || 300;

      const options = {};
      if (fname === 'flag_status') {
        options.sources = currentFlagSources;
        const durInput = document.getElementById('modal-opt-duration_days');
        const minDeadInput = document.getElementById('modal-opt-min_deaths');
        const minCasInput = document.getElementById('modal-opt-min_casualties');
        const stateInput = document.getElementById('modal-opt-state_filter');
        if (durInput) options.duration_days = parseInt(durInput.value, 10) || 4;
        if (minDeadInput) options.min_deaths = parseInt(minDeadInput.value, 10) || 1;
        if (minCasInput) options.min_casualties = parseInt(minCasInput.value, 10) || 1;
        if (stateInput) options.state_filter = stateInput.value.trim();
      } else if (featureModalSuboptions) {
        featureModalSuboptions.querySelectorAll('.modal-sub-opt-input').forEach(input => {
          const k = input.getAttribute('data-opt-key');
          if (!k) return;
          if (input.type === 'checkbox') {
            options[k] = input.checked;
          } else if (input.type === 'number') {
            const v = parseFloat(input.value);
            options[k] = isNaN(v) ? 0 : v;
          } else {
            options[k] = input.value.trim();
          }
        });
      }

      const payload = {
        [fname]: {
          enabled,
          interval_seconds,
          notify_mode,
          batch_interval_seconds,
          options
        }
      };

      if (btnSaveFeatureModal) {
        btnSaveFeatureModal.disabled = true;
        btnSaveFeatureModal.textContent = 'Saving...';
      }

      try {
        const res = await fetch('/api/features', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          const title = featureMeta[fname]?.title || fname;
          showToast(`✓ ${title} configuration saved`);
          closeFeatureModal();
          await loadFeatures();
          await loadStatus();
        } else {
          showToast(`Error: ${data.error || 'Failed to save configuration'}`);
        }
      } catch (err) {
        showToast(`Save failed: ${err}`);
      } finally {
        if (btnSaveFeatureModal) {
          btnSaveFeatureModal.disabled = false;
          btnSaveFeatureModal.textContent = 'Save Configuration';
        }
      }
    });
  }

  // --- Button Handlers ---

  // Trigger Subnet Scan
  async function triggerScan() {
    showToast('Subnet scan initiated, sweeping network...');
    btnTriggerScan.disabled = true;
    btnRunDiscoveryScan.disabled = true;
    try {
      const res = await fetch('/api/discovery/scan', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        showToast(`Scan complete: found ${data.count} active hosts`);
        await loadDiscovery();
        await loadStatus();
      } else {
        showToast(`Scan error: ${data.error}`);
      }
    } catch (e) {
      showToast(`Scan request failed: ${e}`);
    } finally {
      btnTriggerScan.disabled = false;
      btnRunDiscoveryScan.disabled = false;
    }
  }

  btnTriggerScan.addEventListener('click', triggerScan);
  btnRunDiscoveryScan.addEventListener('click', triggerScan);

  // Check Devices Now
  btnCheckDevices.addEventListener('click', async () => {
    showToast('Checking reachability of all configured devices...');
    btnCheckDevices.disabled = true;
    try {
      const res = await fetch('/api/devices/check', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        showToast(`Check complete: monitored ${data.count} devices`);
        await loadDevices();
        await loadServices();
        await loadStatus();
      } else {
        showToast(`Error: ${data.error}`);
      }
    } catch (e) {
      showToast(`Request failed: ${e}`);
    } finally {
      btnCheckDevices.disabled = false;
    }
  });

  // Flush Batched Digest
  btnFlushBatch.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/notifications/flush', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        showToast(`Flushed ${data.count} queued batch notifications to Telegram`);
        await loadStatus();
      }
    } catch (e) {
      showToast(`Flush failed: ${e}`);
    }
  });

  // Refresh External IP
  const btnRefreshIp = document.getElementById('btn-refresh-ip');
  if (btnRefreshIp) {
    btnRefreshIp.addEventListener('click', async () => {
      btnRefreshIp.disabled = true;
      btnRefreshIp.textContent = '...';
      try {
        const res = await fetch('/api/ip/refresh', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          showToast(`Public IP: ${data.ip || 'Checked'}`);
          await loadStatus();
        } else {
          showToast(`IP check failed: ${data.error}`);
        }
      } catch (e) {
        showToast(`Request failed: ${e}`);
      } finally {
        btnRefreshIp.disabled = false;
        btnRefreshIp.textContent = '↻ Check';
      }
    });
  }

  // Send Test Telegram
  btnSendTestTg.addEventListener('click', async () => {
    const input = document.getElementById('tg-test-input');
    const msg = input.value.trim() || 'Test notification from HomeNotifications Web UI';
    try {
      const res = await fetch('/api/notifications/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
      });
      const data = await res.json();
      if (data.success) {
        showToast('✓ Test alert transmitted to Telegram chat');
      } else {
        showToast('❌ Telegram alert failed. Check BOT token and CHATID in config.ini');
      }
    } catch (e) {
      showToast(`Test failed: ${e}`);
    }
  });

  // Flag Dashboard Action Buttons
  const btnToggleFlagTable = document.getElementById('btn-toggle-flag-table');
  const flagTableWrapper = document.getElementById('flag-table-wrapper');
  if (btnToggleFlagTable && flagTableWrapper) {
    btnToggleFlagTable.addEventListener('click', () => {
      const isHidden = flagTableWrapper.style.display === 'none' || !flagTableWrapper.style.display;
      flagTableWrapper.style.display = isHidden ? 'block' : 'none';
      btnToggleFlagTable.textContent = isHidden ? 'Hide Table' : 'Show Table';
    });
  }

  const btnDashboardFlagCheck = document.getElementById('btn-dashboard-flag-check');
  if (btnDashboardFlagCheck) {
    btnDashboardFlagCheck.addEventListener('click', async () => {
      btnDashboardFlagCheck.disabled = true;
      btnDashboardFlagCheck.textContent = 'Checking...';
      try {
        const res = await fetch('/api/flag/check', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          showToast('✓ Flag status updated');
          await loadStatus();
        } else {
          showToast(`Flag check failed: ${data.error}`);
        }
      } catch (err) {
        showToast(`Request failed: ${err}`);
      } finally {
        btnDashboardFlagCheck.disabled = false;
        btnDashboardFlagCheck.textContent = '⚡ Check Now';
      }
    });
  }

  const btnDashboardFlagConfig = document.getElementById('btn-dashboard-flag-config');
  if (btnDashboardFlagConfig) {
    btnDashboardFlagConfig.addEventListener('click', () => {
      openFeatureModal('flag_status');
    });
  }

  // --- Speedtest Modal & Comparison Handlers ---

  function formatTimestamp(ts) {
    if (!ts) return 'Never';
    const d = new Date(ts * 1000);
    const now = Date.now();
    const diffSec = Math.floor((now - d.getTime()) / 1000);
    let rel = '';
    if (diffSec < 60) rel = `${diffSec}s ago`;
    else if (diffSec < 3600) rel = `${Math.floor(diffSec / 60)}m ago`;
    else if (diffSec < 86400) rel = `${Math.floor(diffSec / 3600)}h ago`;
    else rel = `${Math.floor(diffSec / 86400)}d ago`;
    return `${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}, ${d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })} (${rel})`;
  }

  function renderSpeedtestComparison(data) {
    if (!speedtestComparisonContainer) return;
    const curr = data?.current;
    const prev = data?.previous;
    const comp = data?.comparison;

    if (!curr) {
      speedtestComparisonContainer.innerHTML = `
        <div style="background: var(--bg-card); border: 1px dashed var(--border-color); border-radius: var(--radius-md); padding: 32px 20px; text-align: center;">
          <div style="font-size: 32px; margin-bottom: 8px;">⚡</div>
          <h4 style="margin: 0 0 6px 0; font-size: 15px;">No Speedtest Results Recorded</h4>
          <p style="margin: 0; color: var(--text-muted); font-size: 13px;">Click "Run Test Now" above to measure bandwidth throughput and multi-target latency.</p>
        </div>
      `;
      return;
    }

    const currDateStr = formatTimestamp(curr.timestamp);
    const currServer = curr.server?.location || curr.server?.name || (curr.provider === 'ookla' ? 'Ookla Speed Server' : 'Cloudflare Edge');
    const currSponsor = curr.server?.sponsor ? `(${escapeHtml(curr.server.sponsor)})` : '';
    const currClient = curr.client?.ip ? `Client: ${escapeHtml(curr.client.ip)} ${curr.client.isp ? `• ${escapeHtml(curr.client.isp)}` : ''}` : '';

    let prevCardHtml = '';
    if (prev) {
      const prevDateStr = formatTimestamp(prev.timestamp);
      const prevServer = prev.server?.location || prev.server?.name || (prev.provider === 'ookla' ? 'Ookla Speed Server' : 'Cloudflare Edge');

      const dlDelta = comp?.download_delta_mbps ?? 0;
      const dlPct = comp?.download_delta_pct ?? 0;
      const dlClass = dlDelta >= 0 ? 'color: var(--success-text);' : 'color: var(--danger-text);';
      const dlSign = dlDelta >= 0 ? '+' : '';
      const dlArrow = dlDelta >= 0 ? '↑' : '↓';
      const dlPill = comp ? `<div style="${dlClass} font-size: 11px; margin-top: 3px; font-weight: 600;">${dlSign}${dlDelta} Mbps (${dlSign}${dlPct}%) ${dlArrow}</div>` : '';

      const ulDelta = comp?.upload_delta_mbps ?? 0;
      const ulPct = comp?.upload_delta_pct ?? 0;
      const ulClass = ulDelta >= 0 ? 'color: var(--success-text);' : 'color: var(--danger-text);';
      const ulSign = ulDelta >= 0 ? '+' : '';
      const ulArrow = ulDelta >= 0 ? '↑' : '↓';
      const ulPill = comp ? `<div style="${ulClass} font-size: 11px; margin-top: 3px; font-weight: 600;">${ulSign}${ulDelta} Mbps (${ulSign}${ulPct}%) ${ulArrow}</div>` : '';

      const latDelta = comp?.latency_delta_ms ?? 0;
      const latClass = latDelta <= 0 ? 'color: var(--success-text);' : 'color: var(--danger-text);';
      const latSign = latDelta > 0 ? '+' : '';
      const latArrow = latDelta <= 0 ? '↓ faster' : '↑ slower';
      const latPill = comp ? `<div style="${latClass} font-size: 11px; margin-top: 3px; font-weight: 600;">${latSign}${latDelta} ms ${latArrow}</div>` : '';

      prevCardHtml = `
        <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--border-color);">
            <div>
              <div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: var(--text-muted); letter-spacing: 0.5px;">Last Test Result (Previous)</div>
              <div style="font-size: 13px; font-weight: 600; margin-top: 2px;">${prevDateStr}</div>
            </div>
            <span class="badge badge-secondary" style="font-size: 10.5px;">Comparison</span>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 12px; text-align: center;">
            <div style="background: var(--border-subtle); padding: 10px 8px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
              <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 2px;">📥 Download</div>
              <div style="font-size: 16px; font-weight: 700;" class="mono">${prev.download_mbps || 0} <span style="font-size: 11px; font-weight: normal;">Mbps</span></div>
              ${dlPill}
            </div>
            <div style="background: var(--border-subtle); padding: 10px 8px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
              <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 2px;">📤 Upload</div>
              <div style="font-size: 16px; font-weight: 700;" class="mono">${prev.upload_mbps || 0} <span style="font-size: 11px; font-weight: normal;">Mbps</span></div>
              ${ulPill}
            </div>
            <div style="background: var(--border-subtle); padding: 10px 8px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
              <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 2px;">⏱️ Latency</div>
              <div style="font-size: 16px; font-weight: 700;" class="mono">${prev.latency_ms || 0} <span style="font-size: 11px; font-weight: normal;">ms</span></div>
              ${latPill}
            </div>
          </div>

          <div style="font-size: 11.5px; color: var(--text-muted); display: flex; justify-content: space-between; align-items: center;">
            <span>Server: <strong>${escapeHtml(prevServer)}</strong></span>
            <span>Provider: ${escapeHtml(prev.provider?.toUpperCase() || 'WAN')}</span>
          </div>
        </div>
      `;
    } else {
      prevCardHtml = `
        <div style="background: var(--bg-card); border: 1px dashed var(--border-color); border-radius: var(--radius-md); padding: 16px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
          <div style="font-size: 24px; margin-bottom: 6px; color: var(--text-muted);">📊</div>
          <div style="font-size: 13px; font-weight: 600; margin-bottom: 4px;">Initial Recorded Run</div>
          <div style="font-size: 11.5px; color: var(--text-muted); max-width: 260px;">Run another test to compare throughput and latency deltas side-by-side with timestamps.</div>
        </div>
      `;
    }

    speedtestComparisonContainer.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 14px;">
        <!-- Most Recent Test Card -->
        <div style="background: var(--bg-card); border: 2px solid var(--primary); border-radius: var(--radius-md); padding: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--border-color);">
            <div>
              <div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: var(--primary); letter-spacing: 0.5px;">Most Recent Test Result</div>
              <div style="font-size: 13px; font-weight: 600; margin-top: 2px;">${currDateStr}</div>
            </div>
            <span class="badge badge-success" style="font-size: 10.5px;">● Latest</span>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 12px; text-align: center;">
            <div style="background: var(--border-subtle); padding: 10px 8px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
              <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 2px;">📥 Download</div>
              <div style="font-size: 18px; font-weight: 700; color: var(--text-main);" class="mono">${curr.download_mbps || 0} <span style="font-size: 11px; font-weight: normal;">Mbps</span></div>
            </div>
            <div style="background: var(--border-subtle); padding: 10px 8px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
              <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 2px;">📤 Upload</div>
              <div style="font-size: 18px; font-weight: 700; color: var(--text-main);" class="mono">${curr.upload_mbps || 0} <span style="font-size: 11px; font-weight: normal;">Mbps</span></div>
            </div>
            <div style="background: var(--border-subtle); padding: 10px 8px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
              <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 2px;">⏱️ Latency</div>
              <div style="font-size: 18px; font-weight: 700; color: var(--text-main);" class="mono">${curr.latency_ms || 0} <span style="font-size: 11px; font-weight: normal;">ms</span></div>
            </div>
          </div>

          <div style="font-size: 11.5px; color: var(--text-muted); display: flex; flex-direction: column; gap: 3px;">
            <div>Server: <strong>${escapeHtml(currServer)}</strong> ${currSponsor}</div>
            ${currClient ? `<div>${currClient}</div>` : ''}
          </div>
        </div>

        <!-- Previous Test Card -->
        ${prevCardHtml}
      </div>
    `;
  }

  function renderSpeedtestTargetsTable(current, previous, comparison) {
    if (!speedtestTargetsTbody) return;
    const cTargets = current?.target_latencies || {};
    const pTargets = previous?.target_latencies || {};
    const compTargets = comparison?.targets || {};
    const allKeys = Array.from(new Set([...Object.keys(cTargets), ...Object.keys(pTargets)]));

    if (speedtestTargetsCount) {
      speedtestTargetsCount.textContent = `${allKeys.length} target${allKeys.length === 1 ? '' : 's'}`;
    }

    if (allKeys.length === 0) {
      speedtestTargetsTbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No custom latency targets configured. Add targets below in configuration.</td></tr>`;
      return;
    }

    speedtestTargetsTbody.innerHTML = allKeys.map(k => {
      const c = cTargets[k] || {};
      const p = pTargets[k] || {};
      const diff = compTargets[k];

      const status = c.status || 'UNKNOWN';
      const statusBadge = status === 'UP'
        ? '<span class="badge badge-success" style="font-size: 10px;">● Reachable</span>'
        : (status === 'DOWN' ? '<span class="badge badge-danger" style="font-size: 10px;">▲ Unreachable</span>' : '<span class="badge badge-warning" style="font-size: 10px;">? Pending</span>');

      const cLatStr = (c.latency_ms !== undefined && c.latency_ms > 0) ? `${c.latency_ms.toFixed(1)} ms` : (status === 'DOWN' ? 'Timeout' : '—');
      const pLatStr = (p.latency_ms !== undefined && p.latency_ms > 0) ? `${p.latency_ms.toFixed(1)} ms` : (p.status === 'DOWN' ? 'Timeout' : '—');

      let deltaStr = '—';
      if (diff && diff.delta_ms !== null && diff.delta_ms !== undefined) {
        const d = diff.delta_ms;
        const isFaster = d <= 0;
        const color = isFaster ? 'var(--success-text)' : 'var(--danger-text)';
        const sign = d > 0 ? '+' : '';
        const arrow = isFaster ? '↓ faster' : '↑ slower';
        deltaStr = `<span style="color: ${color}; font-weight: 600;" class="mono">${sign}${d.toFixed(1)} ms ${arrow}</span>`;
      }

      return `
        <tr>
          <td><strong>${escapeHtml(k)}</strong></td>
          <td>${statusBadge}</td>
          <td><span class="mono" style="font-weight: 600;">${cLatStr}</span></td>
          <td><span class="mono text-muted">${pLatStr}</span></td>
          <td>${deltaStr}</td>
        </tr>
      `;
    }).join('');
  }

  async function loadSpeedtestResults() {
    try {
      const res = await fetch('/api/speedtest/results');
      const data = await res.json();
      if (!data.success) return;

      renderSpeedtestComparison(data);
      renderSpeedtestTargetsTable(data.current, data.previous, data.comparison);

      // Populate config form fields
      const cfg = data.config || {};
      const provSelect = document.getElementById('st-cfg-provider');
      const srvIdInput = document.getElementById('st-cfg-server-id');
      const targetsInput = document.getElementById('st-cfg-latency-targets');
      const minDlInput = document.getElementById('st-cfg-min-download');
      const minUlInput = document.getElementById('st-cfg-min-upload');
      const maxLatInput = document.getElementById('st-cfg-max-latency');
      const alertDegChk = document.getElementById('st-cfg-alert-degraded');

      if (provSelect && cfg.provider) provSelect.value = cfg.provider;
      if (srvIdInput && cfg.server_id !== undefined) srvIdInput.value = cfg.server_id;
      if (targetsInput && cfg.latency_targets !== undefined) targetsInput.value = cfg.latency_targets;
      if (minDlInput && cfg.min_download_mbps !== undefined) minDlInput.value = cfg.min_download_mbps;
      if (minUlInput && cfg.min_upload_mbps !== undefined) minUlInput.value = cfg.min_upload_mbps;
      if (maxLatInput && cfg.max_latency_ms !== undefined) maxLatInput.value = cfg.max_latency_ms;
      if (alertDegChk && cfg.alert_on_degraded !== undefined) alertDegChk.checked = !!cfg.alert_on_degraded;
    } catch (e) {
      console.error('Failed to load speedtest results:', e);
    }
  }

  let isRunningSpeedtest = false;
  async function runSpeedtest(customOptions = null) {
    if (isRunningSpeedtest) return;
    isRunningSpeedtest = true;

    if (btnRunSpeedtestModal) {
      btnRunSpeedtestModal.disabled = true;
      const textSpan = document.getElementById('speedtest-btn-text');
      const iconSpan = document.getElementById('speedtest-btn-icon');
      if (textSpan) textSpan.textContent = 'Testing Speed & Latency...';
      if (iconSpan) iconSpan.textContent = '⏳';
    }

    if (speedtestStatusHeadline) {
      speedtestStatusHeadline.textContent = 'Speed & Latency Test in Progress...';
    }
    if (speedtestStatusSub) {
      speedtestStatusSub.textContent = 'Step 1/2: Probing latency against configured targets... Step 2/2: Measuring download & upload bandwidth...';
    }

    showToast('⚡ Running Speedtest & Latency check...');

    const payload = customOptions || {
      provider: document.getElementById('st-cfg-provider')?.value || 'ookla',
      server_id: document.getElementById('st-cfg-server-id')?.value?.trim() || '',
      latency_targets: document.getElementById('st-cfg-latency-targets')?.value?.trim() || '1.1.1.1, 8.8.8.8, 9.9.9.9'
    };

    const startTime = Date.now();
    try {
      const res = await fetch('/api/speedtest/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      const elapsedSec = ((Date.now() - startTime) / 1000).toFixed(1);

      if (data.success && data.result) {
        const r = data.result;
        showToast(`✓ Speedtest done (${elapsedSec}s): ↓${r.download_mbps} Mbps, ↑${r.upload_mbps} Mbps, ⏱️${r.latency_ms}ms`);
        if (speedtestStatusHeadline) {
          speedtestStatusHeadline.textContent = `✓ Completed in ${elapsedSec}s: ↓${r.download_mbps} Mbps • ↑${r.upload_mbps} Mbps • ⏱️${r.latency_ms}ms`;
        }
        if (speedtestStatusSub) {
          const srvName = r.server?.location || r.server?.name || r.provider;
          speedtestStatusSub.textContent = `Tested via ${escapeHtml(srvName)} • ${Object.keys(r.target_latencies || {}).length} latency targets verified`;
        }
        await loadSpeedtestResults();
        await loadStatus();
      } else {
        showToast(`Speedtest failed: ${data.error || 'Unknown error'}`);
        if (speedtestStatusHeadline) speedtestStatusHeadline.textContent = 'Speedtest Failed';
        if (speedtestStatusSub) speedtestStatusSub.textContent = data.error || 'Test timed out or could not reach server.';
      }
    } catch (err) {
      showToast(`Speedtest error: ${err}`);
      if (speedtestStatusHeadline) speedtestStatusHeadline.textContent = 'Speedtest Request Error';
      if (speedtestStatusSub) speedtestStatusSub.textContent = String(err);
    } finally {
      isRunningSpeedtest = false;
      if (btnRunSpeedtestModal) {
        btnRunSpeedtestModal.disabled = false;
        const textSpan = document.getElementById('speedtest-btn-text');
        const iconSpan = document.getElementById('speedtest-btn-icon');
        if (textSpan) textSpan.textContent = 'Run Test Now';
        if (iconSpan) iconSpan.textContent = '⚡';
      }
    }
  }

  function openSpeedtestModal(updateRoute = true) {
    if (updateRoute) {
      navigateTo('features', 'speedtest', true);
      return;
    }
    if (speedtestModal) {
      speedtestModal.classList.add('open');
      loadSpeedtestResults();
    }
  }

  function closeSpeedtestModal() {
    if (speedtestModal) {
      speedtestModal.classList.remove('open');
    }
    if (window.location.hash.includes('speedtest')) {
      navigateTo('dashboard', null, true);
    } else {
      updateBreadcrumbs(currentTab, null);
    }
  }

  if (btnCloseSpeedtestModal) {
    btnCloseSpeedtestModal.addEventListener('click', closeSpeedtestModal);
  }
  if (btnCloseSpeedtestFooter) {
    btnCloseSpeedtestFooter.addEventListener('click', closeSpeedtestModal);
  }
  if (speedtestModal) {
    speedtestModal.addEventListener('click', (e) => {
      if (e.target === speedtestModal) closeSpeedtestModal();
    });
  }

  if (btnRunSpeedtestModal) {
    btnRunSpeedtestModal.addEventListener('click', () => runSpeedtest());
  }

  if (speedtestConfigToggle && speedtestSettingsForm) {
    speedtestConfigToggle.addEventListener('click', () => {
      const isHidden = speedtestSettingsForm.style.display === 'none' || !speedtestSettingsForm.style.display;
      speedtestSettingsForm.style.display = isHidden ? 'block' : 'none';
      if (speedtestConfigToggleIcon) {
        speedtestConfigToggleIcon.textContent = isHidden ? '▲ Hide Settings' : '▼ Show Settings';
      }
    });
  }

  if (btnDiscoverSpeedtestServers && stServersDropdownContainer && stCfgServersSelect) {
    btnDiscoverSpeedtestServers.addEventListener('click', async () => {
      btnDiscoverSpeedtestServers.disabled = true;
      btnDiscoverSpeedtestServers.textContent = '🔍 Finding...';
      try {
        const res = await fetch('/api/speedtest/servers');
        const data = await res.json();
        if (data.success && data.servers && data.servers.length) {
          stCfgServersSelect.innerHTML = `
            <option value="">-- Select a Nearby Server --</option>
            ${data.servers.map(s => `
              <option value="${escapeHtml(s.id)}">${escapeHtml(s.sponsor)} (${escapeHtml(s.name)}, ${escapeHtml(s.country)}) - ${s.distance_km}km [ID: ${escapeHtml(s.id)}]</option>
            `).join('')}
          `;
          stServersDropdownContainer.style.display = 'block';
          showToast(`Found ${data.servers.length} nearby Ookla test servers`);
        } else {
          showToast('No nearby servers found: ' + (data.error || 'Check internet connection'));
        }
      } catch (err) {
        showToast('Server search failed: ' + err);
      } finally {
        btnDiscoverSpeedtestServers.disabled = false;
        btnDiscoverSpeedtestServers.textContent = '🔍 Find Servers';
      }
    });

    stCfgServersSelect.addEventListener('change', () => {
      const pickedId = stCfgServersSelect.value;
      const srvIdInput = document.getElementById('st-cfg-server-id');
      if (srvIdInput && pickedId) {
        srvIdInput.value = pickedId;
        showToast(`Selected server ID: ${pickedId}`);
      }
    });
  }

  if (speedtestSettingsForm) {
    speedtestSettingsForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const saveBtn = document.getElementById('btn-save-speedtest-settings');
      if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';
      }

      const provider = document.getElementById('st-cfg-provider')?.value || 'ookla';
      const server_id = document.getElementById('st-cfg-server-id')?.value?.trim() || '';
      const latency_targets = document.getElementById('st-cfg-latency-targets')?.value?.trim() || '1.1.1.1, 8.8.8.8, 9.9.9.9';
      const min_download_mbps = parseFloat(document.getElementById('st-cfg-min-download')?.value) || 25.0;
      const min_upload_mbps = parseFloat(document.getElementById('st-cfg-min-upload')?.value) || 5.0;
      const max_latency_ms = parseFloat(document.getElementById('st-cfg-max-latency')?.value) || 120.0;
      const alert_on_degraded = document.getElementById('st-cfg-alert-degraded')?.checked ?? true;

      const payload = {
        speedtest: {
          enabled: true,
          provider,
          server_id,
          latency_targets,
          min_download_mbps,
          min_upload_mbps,
          max_latency_ms,
          alert_on_degraded,
        }
      };

      try {
        const res = await fetch('/api/features', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast('✓ Speedtest configuration saved');
          await loadFeatures();
          await loadStatus();
        } else {
          showToast(`Save failed: ${data.error}`);
        }
      } catch (err) {
        showToast(`Request failed: ${err}`);
      } finally {
        if (saveBtn) {
          saveBtn.disabled = false;
          saveBtn.textContent = '💾 Save Speedtest Settings';
        }
      }
    });
  }

  // Save Features (if present)
  if (btnSaveFeatures) {
    btnSaveFeatures.addEventListener('click', async () => {
      const rows = document.querySelectorAll('.feature-row');
      const payload = {};

      rows.forEach(r => {
        const fname = r.getAttribute('data-feature');
        const intervalInput = r.querySelector('.input-interval');
        const interval = intervalInput ? parseInt(intervalInput.value, 10) : (allFeatures[fname]?.interval_seconds || 300);
        const modeSelect = r.querySelector('.select-mode');
        const mode = modeSelect ? modeSelect.value : (allFeatures[fname]?.notify_mode || 'on_change');
        const toggle = r.querySelector('.feature-enabled-toggle');
        const enabled = toggle ? toggle.checked : (allFeatures[fname]?.enabled !== false);
        const options = allFeatures[fname]?.options || {};

        r.querySelectorAll('.sub-opt-input').forEach(input => {
          const k = input.getAttribute('data-opt-key');
          if (!k) return;
          if (input.type === 'checkbox') {
            options[k] = input.checked;
          } else if (input.type === 'number') {
            const v = parseFloat(input.value);
            options[k] = isNaN(v) ? 0 : v;
          } else {
            options[k] = input.value.trim();
          }
        });

        payload[fname] = {
          enabled,
          interval_seconds: interval,
          notify_mode: mode,
          options: options
        };
      });

      try {
        const res = await fetch('/api/features', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast('✓ Feature configurations and sub-options saved to config.ini');
          await loadFeatures();
        } else {
          showToast(`Error: ${data.error}`);
        }
      } catch (e) {
        showToast(`Save failed: ${e}`);
      }
    });
  }

  // --- Telegram Settings & Pause Controls ---
  const btnSaveTelegram = document.getElementById('btn-save-telegram');
  if (btnSaveTelegram) {
    btnSaveTelegram.addEventListener('click', async () => {
      const token = document.getElementById('tg-input-token').value.trim();
      const chatId = document.getElementById('tg-input-chatid').value.trim();
      const parseMode = document.getElementById('tg-select-parse-mode').value;
      const enabled = document.getElementById('tg-toggle-enabled').checked;

      try {
        const res = await fetch('/api/telegram', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            bot_token: token,
            chat_id: chatId,
            parse_mode: parseMode,
            enabled: enabled
          })
        });
        const data = await res.json();
        if (data.success) {
          showToast('✓ Telegram configuration saved to config.ini');
          await loadTelegramConfig();
          await loadStatus();
        } else {
          showToast(`Save failed: ${data.error}`);
        }
      } catch (e) {
        showToast(`Error saving Telegram settings: ${e}`);
      }
    });
  }

  // Toggle token password visibility
  const btnToggleTokenVis = document.getElementById('btn-toggle-token-vis');
  const tgInputToken = document.getElementById('tg-input-token');
  if (btnToggleTokenVis && tgInputToken) {
    btnToggleTokenVis.addEventListener('click', () => {
      const isPwd = tgInputToken.type === 'password';
      tgInputToken.type = isPwd ? 'text' : 'password';
      btnToggleTokenVis.textContent = isPwd ? '🔒' : '👁️';
    });
  }

  // Quick pause buttons
  document.querySelectorAll('.btn-tg-pause').forEach(btn => {
    btn.addEventListener('click', async () => {
      const secs = parseInt(btn.getAttribute('data-secs'), 10);
      try {
        const res = await fetch('/api/telegram/pause', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'pause', duration_seconds: secs })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`⏸️ ${data.message}`);
          await loadTelegramConfig();
          await loadStatus();
        }
      } catch (e) {
        showToast(`Pause error: ${e}`);
      }
    });
  });

  // Resume handlers
  const handleResumeTelegram = async () => {
    try {
      const res = await fetch('/api/telegram/pause', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'resume' })
      });
      const data = await res.json();
      if (data.success) {
        showToast('▶ Telegram notifications resumed');
        await loadTelegramConfig();
        await loadStatus();
      }
    } catch (e) {
      showToast(`Resume error: ${e}`);
    }
  };

  const btnTgResume = document.getElementById('btn-tg-resume');
  if (btnTgResume) btnTgResume.addEventListener('click', handleResumeTelegram);

  const btnGlobalResume = document.getElementById('btn-global-resume');
  if (btnGlobalResume) btnGlobalResume.addEventListener('click', handleResumeTelegram);

  // Device Modal Helpers & Handlers
  const formDevSshEnabled = document.getElementById('form-dev-ssh-enabled');
  const formDevSshFields = document.getElementById('form-dev-ssh-fields');
  if (formDevSshEnabled && formDevSshFields) {
    formDevSshEnabled.addEventListener('change', () => {
      formDevSshFields.style.display = formDevSshEnabled.checked ? 'block' : 'none';
    });
  }

  function populateDeviceForm(dev = null) {
    deviceForm.reset();
    const origIdInput = document.getElementById('form-dev-original-id');
    const idInput = document.getElementById('form-dev-id');
    const nameInput = document.getElementById('form-dev-name');
    const ipInput = document.getElementById('form-dev-ip');
    const macInput = document.getElementById('form-dev-mac');
    const tagsInput = document.getElementById('form-dev-tags');
    const pingInput = document.getElementById('form-dev-ping');
    const pingTimeoutInput = document.getElementById('form-dev-ping-timeout');
    const sshEnabledInput = document.getElementById('form-dev-ssh-enabled');
    const sshFields = document.getElementById('form-dev-ssh-fields');
    const sshUserInput = document.getElementById('form-dev-ssh-user');
    const sshPortInput = document.getElementById('form-dev-ssh-port');
    const sshKeyInput = document.getElementById('form-dev-ssh-key');
    const modalTitle = document.getElementById('modal-title');

    const isExisting = Boolean(dev && dev.id && allDevices.some(d => d.id === dev.id));

    if (dev) {
      modalTitle.textContent = isExisting ? `Edit Monitored Device: ${dev.name}` : `Add Monitored Device: ${dev.name || dev.ip}`;
      origIdInput.value = isExisting ? dev.id : '';
      idInput.value = dev.id || '';
      nameInput.value = dev.name || '';
      ipInput.value = dev.ip || '';
      macInput.value = dev.mac || '';
      tagsInput.value = (dev.tags || []).join(', ');
      pingInput.checked = dev.ping_enabled !== false;
      pingTimeoutInput.value = dev.ping_timeout || 2.0;

      const hasSsh = Boolean(dev.ssh && dev.ssh.enabled);
      sshEnabledInput.checked = hasSsh;
      sshFields.style.display = hasSsh ? 'block' : 'none';
      if (dev.ssh) {
        sshUserInput.value = dev.ssh.username || '';
        sshPortInput.value = dev.ssh.port || 22;
        sshKeyInput.value = dev.ssh.key_path || '';
        const sshSystemdInput = document.getElementById('form-dev-ssh-systemd');
        if (sshSystemdInput) {
          sshSystemdInput.value = (dev.ssh.systemd_services || []).join(', ');
        }
      } else {
        sshUserInput.value = '';
        sshPortInput.value = 22;
        sshKeyInput.value = '';
        const sshSystemdInput = document.getElementById('form-dev-ssh-systemd');
        if (sshSystemdInput) sshSystemdInput.value = '';
      }
    } else {
      modalTitle.textContent = 'Add Monitored Device';
      origIdInput.value = '';
      idInput.value = '';
      nameInput.value = '';
      ipInput.value = '';
      macInput.value = '';
      tagsInput.value = '';
      pingInput.checked = true;
      pingTimeoutInput.value = 2.0;
      sshEnabledInput.checked = false;
      sshFields.style.display = 'none';
      sshUserInput.value = '';
      sshPortInput.value = 22;
      sshKeyInput.value = '';
      const sshSystemdInput = document.getElementById('form-dev-ssh-systemd');
      if (sshSystemdInput) sshSystemdInput.value = '';
    }
  }

  function openDeviceModal(dev = null, updateRoute = true) {
    if (updateRoute) {
      const isExisting = Boolean(dev && dev.id && allDevices.some(d => d.id === dev.id));
      const sub = isExisting ? `edit/${encodeURIComponent(dev.id)}` : 'add';
      navigateTo('devices', sub, true);
      if (!isExisting && dev) {
        populateDeviceForm(dev);
        deviceModal.classList.add('open');
      }
      return;
    }

    populateDeviceForm(dev);
    deviceModal.classList.add('open');
  }

  function closeDeviceModal() {
    if (deviceModal) deviceModal.classList.remove('open');
    if (window.location.hash.startsWith('#devices/')) {
      navigateTo('devices', null, true);
    } else {
      updateBreadcrumbs(currentTab, null);
    }
  }

  btnOpenAddDevice.addEventListener('click', () => {
    openDeviceModal(null);
  });

  btnCloseModal.addEventListener('click', closeDeviceModal);
  btnCancelModal.addEventListener('click', closeDeviceModal);
  if (deviceModal) {
    deviceModal.addEventListener('click', (e) => {
      if (e.target === deviceModal) closeDeviceModal();
    });
  }

  deviceForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const original_id = document.getElementById('form-dev-original-id').value.trim();
    const id = document.getElementById('form-dev-id').value.trim();
    const name = document.getElementById('form-dev-name').value.trim();
    const ip = document.getElementById('form-dev-ip').value.trim();
    const mac = document.getElementById('form-dev-mac').value.trim();
    const tags = document.getElementById('form-dev-tags').value.trim();
    const ping_enabled = document.getElementById('form-dev-ping').checked;
    const ping_timeout = parseFloat(document.getElementById('form-dev-ping-timeout').value) || 2.0;

    const ssh_enabled = document.getElementById('form-dev-ssh-enabled').checked;
    const ssh_user = document.getElementById('form-dev-ssh-user').value.trim();
    const ssh_port = parseInt(document.getElementById('form-dev-ssh-port').value, 10) || 22;
    const ssh_key = document.getElementById('form-dev-ssh-key').value.trim();
    const ssh_systemd_input = document.getElementById('form-dev-ssh-systemd');
    const ssh_systemd = ssh_systemd_input ? ssh_systemd_input.value.split(',').map(s => s.trim()).filter(Boolean) : [];

    const payload = {
      original_id,
      id,
      name,
      ip,
      mac,
      tags,
      ping_enabled,
      ping_timeout,
      ssh: {
        enabled: ssh_enabled,
        username: ssh_user,
        port: ssh_port,
        key_path: ssh_key,
        systemd_services: ssh_systemd
      }
    };

    try {
      const res = await fetch('/api/devices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        showToast(`Device '${name}' saved to devices.yaml`);
        closeDeviceModal();
        await loadDevices();
        await loadServices();
        await loadStatus();
      } else {
        showToast(`Error: ${data.error}`);
      }
    } catch (err) {
      showToast(`Failed to save: ${err}`);
    }
  });

  // Search Filter Listeners
  devicesSearchInput.addEventListener('input', renderDevicesTable);
  discoverySearchInput.addEventListener('input', renderDiscoveryTable);

  // --- Auto-Refresh Timer ---
  function resetTimer() {
    if (refreshTimer) clearInterval(refreshTimer);
    const secs = parseInt(autoRefreshSelect.value, 10);
    if (secs > 0) {
      refreshTimer = setInterval(async () => {
        await loadStatus();
        if (currentTab === 'dashboard') await loadDevices();
        if (currentTab === 'devices') await loadDevices();
        if (currentTab === 'discovery') await loadDiscovery();
        if (currentTab === 'services') await loadServices();
        if (currentTab === 'resources') await loadResources();
      }, secs * 1000);
    }
  }

  autoRefreshSelect.addEventListener('change', resetTimer);

  // Setup Table Header Click Listeners for Sorting
  function setupSortableHeaders() {
    document.querySelectorAll('#devices-table th.sortable').forEach(th => {
      th.addEventListener('click', () => {
        const col = th.getAttribute('data-sort');
        if (devicesSort.column === col) {
          devicesSort.asc = !devicesSort.asc;
        } else {
          devicesSort.column = col;
          devicesSort.asc = true;
        }
        renderDevicesTable();
      });
    });

    document.querySelectorAll('#discovery-table th.sortable').forEach(th => {
      th.addEventListener('click', () => {
        const col = th.getAttribute('data-sort');
        if (discoverySort.column === col) {
          discoverySort.asc = !discoverySort.asc;
        } else {
          discoverySort.column = col;
          discoverySort.asc = true;
        }
        renderDiscoveryTable();
      });
    });

    document.querySelectorAll('#services-table th.sortable').forEach(th => {
      th.addEventListener('click', () => {
        const col = th.getAttribute('data-sort');
        if (servicesSort.column === col) {
          servicesSort.asc = !servicesSort.asc;
        } else {
          servicesSort.column = col;
          servicesSort.asc = true;
        }
        renderServicesTable();
      });
    });
  }

  // Global Escape key to dismiss modals
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (featureModal && featureModal.classList.contains('open')) {
        closeFeatureModal();
      }
      if (deviceModal && deviceModal.classList.contains('open')) {
        closeDeviceModal();
      }
      if (serviceModal && serviceModal.classList.contains('open')) {
        closeServiceModal();
      }
      if (speedtestModal && speedtestModal.classList.contains('open')) {
        closeSpeedtestModal();
      }
      if (processModal && processModal.classList.contains('open')) {
        closeProcessModal();
      }
    }
  });

  // Dashboard Monitoring Features Filter Chips
  const dashFilterChips = document.getElementById('dashboard-features-filter-chips');
  if (dashFilterChips) {
    dashFilterChips.querySelectorAll('.chip').forEach(btn => {
      btn.addEventListener('click', () => {
        dashFilterChips.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        dashFeatureFilter = btn.getAttribute('data-dash-cat') || 'all';
        renderDashboardFeatureTiles();
      });
    });
  }

  // --- Initial Route & Data Load ---
  setupSortableHeaders();

  const savedRoute = localStorage.getItem('homenotify_last_route');
  const initialHash = window.location.hash || savedRoute || '#dashboard';
  const { tab: initTab, sub: initSub } = parseRoute(initialHash);
  navigateTo(initTab, initSub, true);

  loadStatus();
  loadTelegramConfig();
  loadDevices();
  loadDiscovery();
  loadServices();
  loadResources();
  loadFeatures();
  resetTimer();
});
