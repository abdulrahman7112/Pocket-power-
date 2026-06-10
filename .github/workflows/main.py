# ============================================================
#  Pocket Option Bot — WebView APK
#  Python + Kivy + Android WebView + JavaScript Injection
# ============================================================

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.switch import Switch
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.utils import platform
from kivy.core.window import Window
from kivy.properties import StringProperty, NumericProperty, BooleanProperty

import threading
import json
import time
import math
import random
from datetime import datetime

# ─── ألوان التطبيق ───
C_BG      = (0.03, 0.07, 0.12, 1)
C_SURFACE = (0.05, 0.12, 0.20, 1)
C_CYAN    = (0.00, 0.80, 1.00, 1)
C_GREEN   = (0.00, 0.90, 0.47, 1)
C_RED     = (1.00, 0.24, 0.34, 1)
C_GOLD    = (1.00, 0.70, 0.00, 1)
C_MUTED   = (0.24, 0.42, 0.50, 1)
C_TEXT    = (0.80, 0.93, 0.96, 1)

# ─── JavaScript الذي يُحقن في Pocket Option ───
INJECT_JS = """
(function() {
  // ═══ قراءة بيانات الشموع ═══
  window._botGetCandles = function() {
    try {
      // محاولة 1: ChartIQ
      var chart = window.CIQ && window.CIQ.ChartEngine 
                  && Object.values(window.CIQ.ChartEngine.registeredContainers||{})[0];
      if (chart && chart.masterData) {
        return chart.masterData.slice(-50).map(function(c) {
          return { o: c.Open, h: c.High, l: c.Low, c: c.Close, t: c.DT };
        });
      }
    } catch(e) {}
    try {
      // محاولة 2: window.chartData  
      if (window.chartData && window.chartData.length)
        return window.chartData.slice(-50);
    } catch(e) {}
    try {
      // محاولة 3: قراءة السعر الحالي من DOM
      var priceEl = document.querySelector(
        '.current-price, .price-value, [class*="currentPrice"], [class*="lastPrice"]'
      );
      if (priceEl) return [{ c: parseFloat(priceEl.textContent) }];
    } catch(e) {}
    return [];
  };

  // ═══ قراءة السعر الحالي ═══  
  window._botGetPrice = function() {
    try {
      var el = document.querySelector(
        '.current-price__value, .price, [data-id="currentPrice"], ' +
        '.chart-header__price, .ticker__price'
      );
      if (el) return parseFloat(el.textContent.replace(/[^0-9.]/g,''));
    } catch(e) {}
    return 0;
  };

  // ═══ تحديد المبلغ ═══
  window._botSetAmount = function(amount) {
    try {
      var inputs = document.querySelectorAll(
        'input[name="amount"], .deal-amount input, ' +
        '[class*="amount"] input, [class*="Amount"] input'
      );
      inputs.forEach(function(inp) {
        var nativeInput = Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype, 'value'
        );
        nativeInput.set.call(inp, amount);
        inp.dispatchEvent(new Event('input',  { bubbles: true }));
        inp.dispatchEvent(new Event('change', { bubbles: true }));
      });
      return inputs.length > 0;
    } catch(e) { return false; }
  };

  // ═══ ضغط BUY ═══
  window._botClickBuy = function() {
    try {
      var btn = document.querySelector(
        'button[data-direction="call"], .btn-call, ' +
        '.deals__btn--call, [class*="buyButton"], ' +
        '[class*="call-btn"], .action-button--call, ' +
        'button.up, button.call'
      );
      if (btn) { btn.click(); return true; }
    } catch(e) {}
    return false;
  };

  // ═══ ضغط SELL ═══
  window._botClickSell = function() {
    try {
      var btn = document.querySelector(
        'button[data-direction="put"], .btn-put, ' +
        '.deals__btn--put, [class*="sellButton"], ' +
        '[class*="put-btn"], .action-button--put, ' +
        'button.down, button.put'
      );
      if (btn) { btn.click(); return true; }
    } catch(e) {}
    return false;
  };

  // ═══ قراءة نتيجة الصفقة ═══
  window._botGetResult = function() {
    try {
      var win  = document.querySelector('.deal-result-win,  [class*="win"],  .profit-positive');
      var loss = document.querySelector('.deal-result-loss, [class*="loss"], .profit-negative');
      if (win  && win.offsetParent)  return 'win';
      if (loss && loss.offsetParent) return 'loss';
    } catch(e) {}
    return 'pending';
  };

  // ═══ قراءة رصيد الحساب ═══
  window._botGetBalance = function() {
    try {
      var el = document.querySelector(
        '.balance-value, [class*="balance"], .account-balance'
      );
      if (el) return parseFloat(el.textContent.replace(/[^0-9.]/g,''));
    } catch(e) {}
    return 0;
  };

  // ═══ تأكيد الحقن ═══
  window._botReady = true;
  console.log('[BOT] JavaScript bridge injected OK');
})();
"""

# ══════════════════════════════════════════════════════
#  محرك التحليل الفني
# ══════════════════════════════════════════════════════
class TechnicalEngine:
    """يحسب المؤشرات الفنية على بيانات الشموع"""

    @staticmethod
    def rsi(prices, period=14):
        if len(prices) < period + 1:
            return 50.0
        gains, losses = 0, 0
        for i in range(len(prices) - period, len(prices)):
            d = prices[i] - prices[i-1]
            if d > 0: gains += d
            else: losses -= d
        if losses == 0: return 100.0
        rs = (gains / period) / (losses / period)
        return round(100 - (100 / (1 + rs)), 2)

    @staticmethod
    def ema(prices, period):
        if len(prices) < period:
            return prices[-1] if prices else 0
        k = 2 / (period + 1)
        e = sum(prices[:period]) / period
        for p in prices[period:]:
            e = p * k + e * (1 - k)
        return round(e, 5)

    @staticmethod
    def bollinger(prices, period=20):
        if len(prices) < period:
            return None, None, None
        window = prices[-period:]
        mid = sum(window) / period
        std = math.sqrt(sum((p - mid)**2 for p in window) / period)
        return round(mid - 2*std, 5), round(mid, 5), round(mid + 2*std, 5)

    @staticmethod
    def stochastic(prices, period=14):
        if len(prices) < period:
            return 50.0
        window = prices[-period:]
        mn, mx = min(window), max(window)
        if mx == mn: return 50.0
        return round(((prices[-1] - mn) / (mx - mn)) * 100, 1)

    @staticmethod
    def analyze(prices):
        """تحليل شامل — يُعيد dict بكل المؤشرات والإشارة"""
        if len(prices) < 21:
            return {'signal': 'WAIT', 'confidence': 0, 'reason': 'بيانات غير كافية'}

        rsi_val  = TechnicalEngine.rsi(prices)
        ema9     = TechnicalEngine.ema(prices, 9)
        ema21    = TechnicalEngine.ema(prices, 21)
        stoch    = TechnicalEngine.stochastic(prices)
        bb_lo, bb_mid, bb_hi = TechnicalEngine.bollinger(prices)
        last     = prices[-1]
        momentum = last - prices[-5] if len(prices) >= 5 else 0

        score = 0

        # RSI
        if rsi_val < 30:   score += 2.5   # oversold → BUY
        elif rsi_val < 40: score += 1.0
        elif rsi_val > 70: score -= 2.5   # overbought → SELL
        elif rsi_val > 60: score -= 1.0

        # EMA Cross
        if ema9 > ema21:   score += 1.5
        else:              score -= 1.5

        # Price vs EMA9
        if last > ema9:    score += 1.0
        else:              score -= 1.0

        # Stochastic
        if stoch < 20:     score += 1.5
        elif stoch > 80:   score -= 1.5

        # Bollinger Bands
        if bb_lo and last < bb_lo:  score += 2.0
        elif bb_hi and last > bb_hi: score -= 2.0

        # Momentum
        if momentum > 0.0002:   score += 1.0
        elif momentum < -0.0002: score -= 1.0

        # Candle patterns (3 candles)
        if len(prices) >= 3:
            c1, c2, c3 = prices[-3], prices[-2], prices[-1]
            if c3 > c2 > c1: score += 0.8   # 3 صعود
            if c3 < c2 < c1: score -= 0.8   # 3 هبوط

        # حساب الثقة
        max_score = 12.0
        confidence = min(95, max(50, 60 + (abs(score) / max_score) * 35))

        if score > 2.0:
            signal = 'BUY'
        elif score < -2.0:
            signal = 'SELL'
        else:
            signal = 'WAIT'
            confidence = 40 + random.uniform(0, 15)

        reasons = {
            'BUY':  f'RSI={rsi_val} | EMA9>EMA21 | Stoch={stoch}',
            'SELL': f'RSI={rsi_val} | EMA9<EMA21 | Stoch={stoch}',
            'WAIT': 'الإشارات متضاربة — انتظار تأكيد'
        }

        return {
            'signal':     signal,
            'confidence': round(confidence, 1),
            'rsi':        rsi_val,
            'ema9':       ema9,
            'ema21':      ema21,
            'stoch':      stoch,
            'bb_lo':      bb_lo,
            'bb_hi':      bb_hi,
            'last':       last,
            'reason':     reasons[signal],
            'score':      round(score, 2)
        }


# ══════════════════════════════════════════════════════
#  الواجهة الرئيسية — تعمل كـ Overlay فوق WebView
# ══════════════════════════════════════════════════════
class BotOverlay(FloatLayout):
    """
    Overlay شفاف يطفو فوق WebView
    يعرض: الإشارة، المؤشرات، زر التحكم، السجل
    """

    signal_text   = StringProperty('⏳ انتظار')
    signal_color  = 'gold'
    confidence    = NumericProperty(0)
    bot_running   = BooleanProperty(False)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.prices      = []
        self.wins        = 0
        self.losses      = 0
        self.profit      = 0.0
        self.trade_open  = False
        self.base_amount = 10
        self.log_lines   = []

        # Panel سفلي قابل للطي
        self.panel_open = False
        self._build_ui()

    def _build_ui(self):
        # ── زر التحكم العائم (دائماً مرئي) ──
        self.fab = Button(
            text='▶',
            size_hint=(None, None),
            size=(60, 60),
            pos_hint={'right': 0.97, 'y': 0.02},
            background_color=C_GREEN,
            font_size='22sp',
            bold=True
        )
        self.fab.bind(on_press=self._toggle_bot)
        self.add_widget(self.fab)

        # ── زر فتح/إغلاق Panel ──
        self.toggle_btn = Button(
            text='📊',
            size_hint=(None, None),
            size=(50, 50),
            pos_hint={'right': 0.97, 'y': 0.14},
            background_color=C_SURFACE,
            font_size='18sp'
        )
        self.toggle_btn.bind(on_press=lambda x: self._toggle_panel())
        self.add_widget(self.toggle_btn)

        # ── Panel السفلي ──
        self.panel = BoxLayout(
            orientation='vertical',
            size_hint=(1, None),
            height=0,  # مخفي في البداية
            pos_hint={'x': 0, 'y': 0}
        )
        with self.panel.canvas.before:
            Color(0.03, 0.07, 0.14, 0.95)
            self.panel_rect = Rectangle(pos=self.panel.pos, size=self.panel.size)
        self.panel.bind(pos=self._update_rect, size=self._update_rect)

        self._build_panel_content()
        self.add_widget(self.panel)

        # ── شريط الإشارة العلوي ──
        self.sig_bar = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=0,  # مخفي حتى يبدأ البوت
            pos_hint={'x': 0, 'top': 1}
        )
        with self.sig_bar.canvas.before:
            Color(0.03, 0.07, 0.14, 0.90)
            self.sig_rect = Rectangle(pos=self.sig_bar.pos, size=self.sig_bar.size)
        self.sig_bar.bind(pos=self._update_sig_rect, size=self._update_sig_rect)

        self.sig_label = Label(
            text='⏳ انتظار إشارة...',
            font_size='14sp',
            bold=True,
            color=C_GOLD
        )
        self.sig_bar.add_widget(self.sig_label)
        self.add_widget(self.sig_bar)

    def _update_rect(self, inst, val):
        self.panel_rect.pos  = inst.pos
        self.panel_rect.size = inst.size

    def _update_sig_rect(self, inst, val):
        self.sig_rect.pos  = inst.pos
        self.sig_rect.size = inst.size

    def _build_panel_content(self):
        # Stats row
        stats = BoxLayout(size_hint_y=None, height=50, spacing=4, padding=4)
        self.lbl_win  = self._mini_stat('✅ 0',  C_GREEN)
        self.lbl_loss = self._mini_stat('❌ 0',  C_RED)
        self.lbl_wr   = self._mini_stat('🎯 --%', C_CYAN)
        self.lbl_pnl  = self._mini_stat('$0.00', C_GOLD)
        for w in [self.lbl_win, self.lbl_loss, self.lbl_wr, self.lbl_pnl]:
            stats.add_widget(w)
        self.panel.add_widget(stats)

        # Indicators row
        inds = BoxLayout(size_hint_y=None, height=40, spacing=4, padding=4)
        self.lbl_rsi   = self._ind_lbl('RSI: --')
        self.lbl_ema   = self._ind_lbl('EMA: --')
        self.lbl_stoch = self._ind_lbl('Stoch: --')
        self.lbl_conf  = self._ind_lbl('Conf: --%')
        for w in [self.lbl_rsi, self.lbl_ema, self.lbl_stoch, self.lbl_conf]:
            inds.add_widget(w)
        self.panel.add_widget(inds)

        # Controls row
        ctrl = BoxLayout(size_hint_y=None, height=44, spacing=6, padding=[6,2,6,2])

        # Amount
        self.amt_inp = TextInput(
            text='10', multiline=False,
            input_filter='int',
            font_size='14sp',
            size_hint_x=0.25,
            background_color=(0.05, 0.12, 0.20, 1),
            foreground_color=C_TEXT,
            cursor_color=C_CYAN
        )
        # Expiry spinner
        self.exp_spin = Spinner(
            text='15s',
            values=['5s','10s','15s','30s','1m','5m'],
            size_hint_x=0.25,
            background_color=C_SURFACE,
            color=C_CYAN,
            font_size='13sp'
        )
        # Asset spinner
        self.asset_spin = Spinner(
            text='EUR/USD OTC',
            values=['EUR/USD OTC','GBP/USD OTC','USD/JPY OTC','AUD/USD OTC','BTC OTC'],
            size_hint_x=0.50,
            background_color=C_SURFACE,
            color=C_CYAN,
            font_size='11sp'
        )
        ctrl.add_widget(self.amt_inp)
        ctrl.add_widget(self.exp_spin)
        ctrl.add_widget(self.asset_spin)
        self.panel.add_widget(ctrl)

        # Log
        scroll = ScrollView(size_hint_y=None, height=100)
        self.log_label = Label(
            text='[color=4a7a9b]--- سجل البوت ---[/color]',
            markup=True,
            font_size='10sp',
            size_hint_y=None,
            halign='right',
            text_size=(Window.width, None)
        )
        self.log_label.bind(texture_size=lambda i,v: setattr(i,'height',v[1]))
        scroll.add_widget(self.log_label)
        self.panel.add_widget(scroll)

    def _mini_stat(self, text, color):
        lbl = Label(text=text, font_size='12sp', bold=True, color=color)
        return lbl

    def _ind_lbl(self, text):
        lbl = Label(text=text, font_size='10sp', color=C_MUTED)
        return lbl

    def _toggle_panel(self):
        self.panel_open = not self.panel_open
        self.panel.height = 240 if self.panel_open else 0

    def _toggle_bot(self, *a):
        app = App.get_running_app()
        app.toggle_bot()

    def update_signal(self, analysis):
        if not analysis:
            return
        sig  = analysis.get('signal', 'WAIT')
        conf = analysis.get('confidence', 0)

        colors = {'BUY': '[color=00e676]', 'SELL': '[color=ff3d57]', 'WAIT': '[color=ffb300]'}
        emojis = {'BUY': '▲', 'SELL': '▼', 'WAIT': '⏳'}

        col = colors.get(sig, colors['WAIT'])
        emo = emojis.get(sig, '⏳')

        self.sig_label.text = f'{col}{emo} {sig}  {conf:.0f}%[/color]'
        self.sig_label.markup = True
        self.sig_bar.height = 36

        # Indicators
        if 'rsi' in analysis:
            self.lbl_rsi.text   = f'RSI:{analysis["rsi"]:.0f}'
            self.lbl_ema.text   = f'EMA:{"↑" if analysis["ema9"]>analysis["ema21"] else "↓"}'
            self.lbl_stoch.text = f'K:{analysis["stoch"]:.0f}'
            self.lbl_conf.text  = f'{conf:.0f}%'

    def update_stats(self, wins, losses, profit):
        self.wins, self.losses, self.profit = wins, losses, profit
        tot = wins + losses
        wr  = f'{wins/tot*100:.0f}%' if tot else '--%'
        sign = '+' if profit >= 0 else ''
        self.lbl_win.text  = f'✅ {wins}'
        self.lbl_loss.text = f'❌ {losses}'
        self.lbl_wr.text   = f'🎯 {wr}'
        self.lbl_pnl.text  = f'{sign}${profit:.2f}'
        self.lbl_pnl.color = C_GREEN if profit >= 0 else C_RED

    def add_log(self, msg, kind='info'):
        colors = {'info':'00c8ff','success':'00e676','error':'ff3d57',
                  'warn':'ffb300','ai':'bb86fc'}
        c = colors.get(kind, 'cccccc')
        now = datetime.now().strftime('%H:%M:%S')
        self.log_lines.append(f'[color={c}]{now} {msg}[/color]')
        if len(self.log_lines) > 80:
            self.log_lines = self.log_lines[-80:]
        self.log_label.text = '\n'.join(reversed(self.log_lines))

    def set_bot_active(self, active):
        self.bot_running = active
        self.fab.text = '⏹' if active else '▶'
        self.fab.background_color = C_RED if active else C_GREEN


# ══════════════════════════════════════════════════════
#  التطبيق الرئيسي
# ══════════════════════════════════════════════════════
class PocketOptionBotApp(App):
    title = 'Pocket Option Bot'

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bot_running  = False
        self.prices       = []
        self.wins         = 0
        self.losses       = 0
        self.profit       = 0.0
        self.base_amount  = 10
        self.trade_active = False
        self.webview      = None
        self.overlay      = None
        self.tick_count   = 0
        self.use_real_wv  = (platform == 'android')

    def build(self):
        Window.clearcolor = C_BG
        root = FloatLayout()

        if self.use_real_wv:
            # ══ Android ══ WebView حقيقي
            wv = self._create_android_webview()
            root.add_widget(wv)
        else:
            # ══ Desktop/Test ══ placeholder
            placeholder = Label(
                text='[b][color=00c8ff]Pocket Option WebView[/color][/b]\n\n'
                     '[color=4a7a9b]سيُفتح هنا على Android\n'
                     'تسجّل الدخول مرة واحدة ← البوت يتحكم تلقائياً[/color]',
                markup=True, font_size='14sp',
                halign='center'
            )
            root.add_widget(placeholder)

        # Overlay البوت
        self.overlay = BotOverlay()
        root.add_widget(self.overlay)

        # تحديث دوري
        Clock.schedule_interval(self._tick, 1.5)

        self.overlay.add_log('التطبيق جاهز', 'info')
        self.overlay.add_log('سجّل الدخول في Pocket Option', 'warn')

        return root

    def _create_android_webview(self):
        """ينشئ WebView حقيقي على Android"""
        from android.runnable import run_on_ui_thread
        from jnius import autoclass

        WebView          = autoclass('android.webkit.WebView')
        WebViewClient    = autoclass('android.webkit.WebViewClient')
        WebSettings      = autoclass('android.webkit.WebSettings')
        KivyActivity     = autoclass('org.kivy.android.PythonActivity')

        activity = KivyActivity.mActivity

        wv = WebView(activity)
        settings = wv.getSettings()
        settings.setJavaScriptEnabled(True)
        settings.setDomStorageEnabled(True)
        settings.setLoadWithOverviewMode(True)
        settings.setUseWideViewPort(True)
        settings.setUserAgentString(
            'Mozilla/5.0 (Linux; Android 12; Samsung Galaxy) '
            'AppleWebKit/537.36 Chrome/112 Mobile Safari/537.36'
        )

        # Bridge: Android ← JavaScript
        wv.addJavascriptInterface(
            self._make_js_bridge(), 'AndroidBridge'
        )

        # عند الانتهاء من تحميل الصفحة → حقن JS
        class BotWebViewClient(WebViewClient):
            def onPageFinished(self_, view, url):
                self._on_page_loaded(view, url)

        wv.setWebViewClient(BotWebViewClient())
        wv.loadUrl('https://pocketoption.com/ar/cabinet/demo-quick-high-low/')

        self.webview = wv

        # تحويل WebView لـ Kivy widget
        from android.runnable import run_on_ui_thread
        from kivy.uix.widget import Widget
        holder = Widget()
        # سيتم إضافة WebView إلى layout Android مباشرة
        return holder

    def _make_js_bridge(self):
        """ينشئ كائن Bridge بين JS وPython"""
        from jnius import PythonJavaClass, java_method

        app = self

        class Bridge(PythonJavaClass):
            __javainterfaces__ = ['java/lang/Object']

            @java_method('([D)V')
            def sendCandles(self_, candles_json):
                try:
                    candles = json.loads(candles_json)
                    closes  = [c.get('c', c.get('close', 0)) for c in candles if c]
                    app.prices = [p for p in closes if p > 0]
                except Exception as e:
                    app.overlay.add_log(f'candles error: {e}', 'error')

            @java_method('(Ljava/lang/String;)V')
            def onTradeResult(self_, result):
                app._handle_trade_result(result)

            @java_method('(D)V')
            def sendPrice(self_, price):
                if price > 0:
                    app.prices.append(price)
                    if len(app.prices) > 300:
                        app.prices = app.prices[-300:]

        return Bridge()

    def _on_page_loaded(self, view, url):
        """يُشغَّل بعد تحميل كل صفحة → حقن JS"""
        self.overlay.add_log(f'صفحة محملة: {url[:40]}', 'info')

        if 'pocketoption' in url:
            # حقن الـ JS bridge
            view.evaluateJavascript(INJECT_JS, None)
            self.overlay.add_log('✅ JavaScript bridge محقون', 'success')

            # بدء قراءة البيانات كل 2 ثانية
            Clock.schedule_interval(lambda dt: self._read_candles(), 2.0)

    def _read_candles(self):
        """يطلب من JS إرسال بيانات الشموع"""
        if self.webview and self.bot_running:
            self.webview.evaluateJavascript(
                'AndroidBridge.sendCandles(JSON.stringify(window._botGetCandles()))',
                None
            )

    # ─── Simulation للاختبار على الكمبيوتر ───
    def _simulate_price(self):
        last = self.prices[-1] if self.prices else 1.16708
        new  = last + (random.random() - 0.494) * 0.00014
        self.prices.append(new)
        if len(self.prices) > 300:
            self.prices = self.prices[-300:]

    def _tick(self, dt):
        """يُشغَّل كل 1.5 ثانية"""
        if not self.use_real_wv:
            # وضع المحاكاة
            self._simulate_price()

        if len(self.prices) < 5:
            return

        # تحليل فني
        analysis = TechnicalEngine.analyze(self.prices)
        Clock.schedule_once(lambda dt: self.overlay.update_signal(analysis), 0)

        self.tick_count += 1

        if self.bot_running and self.tick_count % 7 == 0 and not self.trade_active:
            sig  = analysis['signal']
            conf = analysis['confidence']
            thresh = 65  # يمكن جعله قابلاً للتعديل

            if sig != 'WAIT' and conf >= thresh:
                self._execute_trade(sig, conf, analysis)
            elif sig != 'WAIT':
                Clock.schedule_once(lambda dt:
                    self.overlay.add_log(f'⚠️ ثقة منخفضة {conf:.0f}% < {thresh}%', 'warn'), 0)

    def _execute_trade(self, direction, confidence, analysis):
        """تنفيذ الصفقة"""
        amount = int(self.overlay.amt_inp.text or '10')
        expiry = self.overlay.exp_spin.text
        asset  = self.overlay.asset_spin.text

        self.trade_active = True

        Clock.schedule_once(lambda dt:
            self.overlay.add_log(
                f'📤 {direction} | {asset} | ${amount} | {expiry} | {confidence:.0f}%', 'info'), 0)

        if self.use_real_wv and self.webview:
            # تنفيذ حقيقي عبر JS
            self.webview.evaluateJavascript(
                f'window._botSetAmount({amount})', None)
            time.sleep(0.3)
            if direction == 'BUY':
                self.webview.evaluateJavascript('window._botClickBuy()', None)
            else:
                self.webview.evaluateJavascript('window._botClickSell()', None)
        else:
            # محاكاة النتيجة
            expiry_ms = {'5s':5,'10s':10,'15s':15,'30s':30,'1m':60,'5m':300}
            delay = expiry_ms.get(expiry, 15)
            Clock.schedule_once(
                lambda dt: self._simulate_result(direction, amount, confidence),
                delay
            )

    def _simulate_result(self, direction, amount, confidence):
        """محاكاة نتيجة الصفقة"""
        win_prob = (confidence / 100) * 0.84
        won = random.random() < win_prob
        self._handle_trade_result('win' if won else 'loss', amount)

    def _handle_trade_result(self, result, amount=None):
        """معالجة نتيجة الصفقة"""
        if amount is None:
            amount = int(self.overlay.amt_inp.text or '10')

        self.trade_active = False
        won = (result == 'win')

        if won:
            self.wins  += 1
            payout      = round(amount * 0.92, 2)
            self.profit += payout
            Clock.schedule_once(lambda dt: (
                self.overlay.add_log(f'✅ فائز! +${payout}', 'success'),
                self.overlay.update_stats(self.wins, self.losses, self.profit)
            ), 0)
            # إعادة المبلغ الأساسي
            Clock.schedule_once(lambda dt: setattr(
                self.overlay.amt_inp, 'text', str(self.base_amount)), 0)
        else:
            self.losses += 1
            self.profit -= amount
            Clock.schedule_once(lambda dt: (
                self.overlay.add_log(f'❌ خاسر -${amount}', 'error'),
                self.overlay.update_stats(self.wins, self.losses, self.profit)
            ), 0)

    def toggle_bot(self):
        self.bot_running = not self.bot_running
        self.overlay.set_bot_active(self.bot_running)
        if self.bot_running:
            self.base_amount = int(self.overlay.amt_inp.text or '10')
            self.overlay.add_log('▶ البوت نشط', 'info')
        else:
            self.overlay.add_log('⏹ البوت متوقف', 'warn')


if __name__ == '__main__':
    PocketOptionBotApp().run()
