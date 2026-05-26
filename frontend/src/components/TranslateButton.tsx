import { useState, useCallback, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Languages, Loader2 } from 'lucide-react';

declare global {
  interface Window {
    google: any;
    googleTranslateElementInit: (() => void) | null;
  }
}

const TRANSLATE_COOKIE = 'googtrans=/auto/zh-CN';
const STYLE_ID = 'translate-hide-style';

function injectHideStyle() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    .goog-te-banner-frame { display: none !important; }
    body { top: 0 !important; }
    .goog-logo-link { display: none !important; }
    .goog-te-gadget { height: 0 !important; overflow: hidden !important; }
    #google_translate_element { display: none !important; }
    .skiptranslate { display: none !important; }
  `;
  document.head.appendChild(style);
}

export default function TranslateButton() {
  const [translating, setTranslating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (document.cookie.includes(TRANSLATE_COOKIE)) {
      setTranslating(true);
    }
  }, []);

  const toggle = useCallback(() => {
    if (translating) {
      // Restore original: clear cookie and reload
      document.cookie = 'googtrans=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/';
      window.location.reload();
      return;
    }

    if (window.google?.translate?.TranslateElement) {
      // Already loaded, re-trigger via cookie + reload
      document.cookie = `${TRANSLATE_COOKIE};path=/;SameSite=Lax`;
      window.location.reload();
      return;
    }

    setLoading(true);
    setError(false);
    injectHideStyle();

    // Set cookie before loading script so it auto-translates
    document.cookie = `${TRANSLATE_COOKIE};path=/;SameSite=Lax`;

    const div = document.createElement('div');
    div.id = 'google_translate_element';
    document.body.appendChild(div);

    window.googleTranslateElementInit = () => {
      try {
        new window.google.translate.TranslateElement(
          {
            pageLanguage: 'auto',
            includedLanguages: 'zh-CN',
            autoDisplay: true,
            layout: window.google.translate.TranslateElement.InlineLayout.SIMPLE,
          },
          'google_translate_element'
        );
        setTranslating(true);
      } catch {
        setError(true);
      }
      setLoading(false);
    };

    const script = document.createElement('script');
    script.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
    script.async = true;
    script.onerror = () => {
      setError(true);
      setLoading(false);
    };
    document.head.appendChild(script);
  }, [translating]);

  if (error) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => {
          const url = `https://translate.google.com/translate?hl=zh-CN&sl=auto&u=${encodeURIComponent(window.location.href)}`;
          window.open(url, '_blank', 'noopener,noreferrer');
        }}
        title="内置翻译加载失败，点击使用 Google 翻译网页版"
      >
        <Languages className="h-4 w-4 mr-2" />
        翻译
      </Button>
    );
  }

  return (
    <Button
      variant={translating ? 'default' : 'outline'}
      size="sm"
      onClick={toggle}
      disabled={loading}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
      ) : (
        <Languages className="h-4 w-4 mr-2" />
      )}
      {loading ? '加载中...' : translating ? '显示原文' : '翻译成中文'}
    </Button>
  );
}
