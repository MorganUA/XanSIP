/**
 * SIP CRM WebRTC softphone — ES module, JsSIP loaded on demand.
 */

const STATES = {
  idle: "idle",
  connecting: "connecting",
  registered: "registered",
  calling: "calling",
  ringing: "ringing",
  in_call: "in_call",
  incoming: "incoming",
  error: "error",
};

let jssipModule = null;

async function getJsSIP() {
  if (!jssipModule) {
    jssipModule = await import("https://cdn.jsdelivr.net/npm/jssip@3.10.1/+esm");
  }
  return jssipModule;
}

export class SipSoftphone {
  constructor(hooks = {}) {
    this.hooks = hooks;
    this.ua = null;
    this.session = null;
    this.config = null;
    this.state = STATES.idle;
    this.muted = false;
    this._callStartedAt = null;
    this._durationTimer = null;
    this._incomingSession = null;
    this._JsSIP = null;
  }

  _setState(next, detail = "") {
    this.state = next;
    this.hooks.onStateChange?.(next, detail);
  }

  _uaConfig(sessionConfig) {
    const cfg = {
      sockets: [new this._JsSIP.WebSocketInterface(sessionConfig.wss_url)],
      uri: sessionConfig.uri,
      password: sessionConfig.password,
      display_name: sessionConfig.display_name || sessionConfig.display_number,
      register: true,
      session_timers: false,
      user_agent: "SIPCRM-MiniApp/1.0",
    };
    if (sessionConfig.outbound_proxy) {
      cfg.outbound_proxy_set = sessionConfig.outbound_proxy;
    }
    return cfg;
  }

  _pcConfig(sessionConfig) {
    return {
      iceServers: sessionConfig.ice_servers || [],
      iceTransportPolicy: "all",
    };
  }

  _mediaOptions(sessionConfig) {
    return {
      mediaConstraints: { audio: true, video: false },
      pcConfig: this._pcConfig(sessionConfig),
      rtcOfferConstraints: { offerToReceiveAudio: true, offerToReceiveVideo: false },
    };
  }

  async _ensureMic() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Микрофон недоступен в этом браузере");
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    stream.getTracks().forEach((t) => t.stop());
  }

  async connect(sessionConfig) {
    await this.disconnect(false);
    this.config = sessionConfig;
    this._JsSIP = await getJsSIP();
    await this._ensureMic();
    this._setState(STATES.connecting, "Подключение к SIP…");

    const ua = new this._JsSIP.UA(this._uaConfig(sessionConfig));
    this.ua = ua;

    ua.on("connected", () => this._setState(STATES.connecting, "SIP online"));
    ua.on("disconnected", () => {
      if (this.state !== STATES.idle) this._setState(STATES.error, "Соединение с SIP потеряно");
    });
    ua.on("registered", () => this._setState(STATES.registered, "На линии"));
    ua.on("unregistered", () => {
      if (this.state === STATES.registered) this._setState(STATES.connecting, "Перерегистрация…");
    });
    ua.on("registrationFailed", (e) => {
      this._setState(STATES.error, `Регистрация: ${e?.cause || "failed"}`);
    });
    ua.on("newRTCSession", (data) => this._onNewSession(data));

    ua.start();
  }

  _onNewSession(data) {
    const session = data.session;
    if (session.direction === "incoming") {
      if (this.session && !session.isEnded?.()) {
        session.terminate({ status_code: 486, reason_phrase: "Busy Here" });
        return;
      }
      this._incomingSession = session;
      this._bindSession(session, "inbound");
      this._setState(STATES.incoming, session.remote_identity?.uri?.user || "Входящий");
      this.hooks.onIncoming?.(session.remote_identity?.uri?.user || "unknown");
      return;
    }
    this.session = session;
    this._bindSession(session, "outbound");
  }

  _bindSession(session, direction) {
    session.on("progress", () => {
      this._setState(STATES.ringing, direction === "outbound" ? "Вызов…" : "Звонит…");
    });
    session.on("accepted", () => {
      this._startDuration();
      this._setState(STATES.in_call, "Разговор");
    });
    session.on("confirmed", () => {
      this._startDuration();
      this._setState(STATES.in_call, "Разговор");
    });
    session.on("failed", (e) => {
      this._stopDuration();
      this.hooks.onCallEvent?.({
        direction,
        remote_number: this._remoteNumber(session),
        status: "failed",
        cause: e?.cause || "failed",
      });
      this._clearSession(session);
      this._setState(STATES.registered, e?.cause || "failed");
    });
    session.on("ended", () => {
      const duration = this._stopDuration();
      this.hooks.onCallEvent?.({
        direction,
        remote_number: this._remoteNumber(session),
        status: "ended",
        duration_ms: duration,
      });
      this._clearSession(session);
      this._setState(STATES.registered, "Готов");
    });
  }

  _remoteNumber(session) {
    return session?.remote_identity?.uri?.user || "";
  }

  _dialUri(number) {
    const digits = String(number).replace(/[^\d+*#]/g, "");
    const prefix = this.config?.dial_prefix || "";
    return `sip:${prefix}${digits}@${this.config?.sip_domain}`;
  }

  call(number) {
    if (!this.ua || !this.isRegistered()) throw new Error("SIP не зарегистрирован");
    this._setState(STATES.calling, number);
    const session = this.ua.call(this._dialUri(number), this._mediaOptions(this.config));
    this.session = session;
    this._bindSession(session, "outbound");
    this.hooks.onCallEvent?.({
      direction: "outbound",
      remote_number: String(number).replace(/[^\d+*#]/g, ""),
      status: "started",
    });
  }

  answer() {
    const session = this._incomingSession || this.session;
    if (!session) return;
    session.answer(this._mediaOptions(this.config));
    this.session = session;
    this._incomingSession = null;
  }

  hangup() {
    const session = this.session || this._incomingSession;
    if (session && !session.isEnded()) session.terminate();
    this._incomingSession = null;
    this.session = null;
    this._stopDuration();
    this._setState(this.isRegistered() ? STATES.registered : STATES.idle, this.isRegistered() ? "Готов" : "");
  }

  toggleMute() {
    const session = this.session;
    if (!session) return this.muted;
    if (this.muted) {
      session.unmute({ audio: true });
      this.muted = false;
    } else {
      session.mute({ audio: true });
      this.muted = true;
    }
    return this.muted;
  }

  sendDtmf(tone) {
    this.session?.sendDTMF(tone);
  }

  isRegistered() {
    return this.ua?.isRegistered?.() === true;
  }

  async disconnect(resetState = true) {
    this.hangup();
    if (this.ua) {
      try { this.ua.stop(); } catch (_) { /* noop */ }
    }
    this.ua = null;
    this.config = null;
    this.muted = false;
    if (resetState) this._setState(STATES.idle, "");
  }

  _startDuration() {
    this._callStartedAt = Date.now();
    clearInterval(this._durationTimer);
    this._durationTimer = setInterval(() => {
      if (!this._callStartedAt) return;
      const sec = Math.floor((Date.now() - this._callStartedAt) / 1000);
      this.hooks.onDuration?.(sec);
    }, 1000);
  }

  _stopDuration() {
    clearInterval(this._durationTimer);
    this._durationTimer = null;
    const duration = this._callStartedAt ? Date.now() - this._callStartedAt : 0;
    this._callStartedAt = null;
    return duration;
  }

  _clearSession(session) {
    if (this.session === session) this.session = null;
    if (this._incomingSession === session) this._incomingSession = null;
    this.muted = false;
  }
}

export { STATES as SipSoftphoneStates };
