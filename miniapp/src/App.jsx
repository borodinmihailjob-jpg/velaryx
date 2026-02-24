import { useEffect, useState } from 'react';
import { apiRequest, persistUserLanguageCode, resolveUserLanguageCode } from './api';
import { BottomNav, LoadingScreen } from './components/common/index.jsx';
import CompatibilityTab from './screens/CompatibilityTab.jsx';
import HoroscopeScreen from './screens/HoroscopeScreen.jsx';
import NatalScreen from './screens/NatalScreen.jsx';
import NumerologyScreen from './screens/NumerologyScreen.jsx';
import OnboardingScreen from './screens/OnboardingScreen.jsx';
import OracleTab from './screens/OracleTab.jsx';
import ProfileTab from './screens/ProfileTab.jsx';
import TarotScreen from './screens/TarotScreen.jsx';

// ---------------------------------------------------------------------------
// Navigation model: flat stack on top of tab coordinator
// currentTab: 'oracle' | 'compat' | 'profile'
// screenStack: Array<{ screen: string, props: object }>
// ---------------------------------------------------------------------------

export default function App() {
  const [uiLang, setUiLang] = useState(() => resolveUserLanguageCode());
  const [hasOnboarding, setHasOnboarding] = useState(() => localStorage.getItem('onboarding_complete') === '1');
  const [initLoading, setInitLoading] = useState(true);

  const [currentTab, setCurrentTab] = useState('oracle');
  const [screenStack, setScreenStack] = useState([]);

  // Keep document lang in sync
  useEffect(() => {
    document.documentElement.lang = uiLang;
  }, [uiLang]);

  // Sync language from backend + verify onboarding profile still exists
  useEffect(() => {
    let active = true;

    apiRequest('/v1/users/me')
      .then((data) => {
        if (!active) return;
        if (data?.language_code) {
          const normalized = persistUserLanguageCode(data.language_code);
          setUiLang(normalized);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (active) setInitLoading(false);
      });

    return () => { active = false; };
  }, []);

  // If onboarding flag is set but profile doesn't exist, reset it
  useEffect(() => {
    if (!hasOnboarding) return undefined;

    let active = true;
    apiRequest('/v1/natal/profile/latest')
      .catch((e) => {
        if (!active) return;
        const msg = String(e?.message || e || '').toLowerCase();
        if (e?.status === 404 || msg.includes('not found') || msg.includes('404')) {
          localStorage.removeItem('onboarding_complete');
          setHasOnboarding(false);
        }
      });

    return () => { active = false; };
  }, [hasOnboarding]);

  // ---------------------------------------------------------------------------
  // Navigation helpers
  // ---------------------------------------------------------------------------
  const pushScreen = (screen, props = {}) => {
    setScreenStack((prev) => [...prev, { screen, props }]);
  };

  const popScreen = () => {
    setScreenStack((prev) => prev.slice(0, -1));
  };

  const switchTab = (tab) => {
    setCurrentTab(tab);
    setScreenStack([]);
  };

  // ---------------------------------------------------------------------------
  // Onboarding gate
  // ---------------------------------------------------------------------------
  if (initLoading) {
    return <LoadingScreen />;
  }

  if (!hasOnboarding) {
    return (
      <OnboardingScreen
        mode="create"
        onComplete={() => setHasOnboarding(true)}
      />
    );
  }

  // ---------------------------------------------------------------------------
  // Screen stack: topmost screen wins
  // ---------------------------------------------------------------------------
  const topItem = screenStack[screenStack.length - 1];

  if (topItem) {
    const { screen, props } = topItem;

    if (screen === 'onboarding') {
      return (
        <OnboardingScreen
          mode="edit"
          onBack={popScreen}
          onComplete={() => {
            setHasOnboarding(true);
            popScreen();
          }}
          {...props}
        />
      );
    }

    if (screen === 'horoscope') {
      return <HoroscopeScreen onBack={popScreen} {...props} />;
    }

    if (screen === 'natal') {
      return <NatalScreen onBack={popScreen} {...props} />;
    }

    if (screen === 'tarot') {
      return <TarotScreen onBack={popScreen} {...props} />;
    }

    if (screen === 'numerology') {
      return <NumerologyScreen onBack={popScreen} {...props} />;
    }
  }

  // ---------------------------------------------------------------------------
  // Tab content
  // ---------------------------------------------------------------------------
  let tabContent = null;

  if (currentTab === 'oracle') {
    tabContent = (
      <OracleTab
        hasProfile={hasOnboarding}
        onNavigate={(screen, props) => pushScreen(screen, props)}
      />
    );
  }

  if (currentTab === 'compat') {
    tabContent = <CompatibilityTab />;
  }

  if (currentTab === 'profile') {
    tabContent = (
      <ProfileTab
        onEditProfile={() => pushScreen('onboarding')}
      />
    );
  }

  return (
    <div className="app-shell">
      {tabContent}
      <BottomNav tab={currentTab} setTab={switchTab} />
    </div>
  );
}
