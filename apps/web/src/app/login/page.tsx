"use client";
import { FormEvent, useEffect, useState } from "react";
import { createClient } from "@/lib/auth/client";
import ThemeToggle from "@/components/ThemeToggle";

export default function LoginPage() {
  const [linkError, setLinkError] = useState(false); const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => setLinkError(new URLSearchParams(window.location.search).get("error") === "link"), []);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    const { error } = await createClient().auth.signInWithPassword({ email, password });
    if (error) setMessage(error.message.toLowerCase().includes("confirm") ? "Your evaluator account needs to be confirmed by the project owner." : "Email or password was not accepted. Please try again.");
    else window.location.assign("/call");
    setBusy(false);
  }
  async function magicLink() {
    setBusy(true); setMessage("");
    const { error } = await createClient().auth.signInWithOtp({ email, options: { emailRedirectTo: `${window.location.origin}/auth/callback?next=/call` } });
    setMessage(error ? (error.message.toLowerCase().includes("rate") ? "Too many emails sent. Try again later." : "A sign-in link could not be sent. Use your evaluator password or try again later.") : "If this address is allowed by Supabase's built-in email service, a sign-in link is on its way. This service is limited to project team addresses."); setBusy(false);
  }
  return (
    <main className="auth-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-signal" aria-hidden="true" />
          <span className="brand-line"><span className="brand-name">ARIA</span><span className="brand-divider">//</span><span className="brand-product">VOICE CX</span></span>
          <span className="topbar-caption">AURA SKINCARE · EVALUATOR DEMO</span>
        </div>
        <ThemeToggle />
      </header>

      <div className="auth-main">
        <div className="auth-card">
          <section className="auth-story" aria-labelledby="aria-intro-title">
            <div>
              <span className="kicker"><span className="brand-signal" aria-hidden="true" />PRIVATE EVALUATOR ACCESS</span>
              <h1 id="aria-intro-title">Meet Aria, Aura&apos;s support assistant.</h1>
              <p className="auth-story-copy">Explore order tracking, product guidance, and policy-aware support through a voice or text conversation.</p>
            </div>
            <div className="flow-diagram" aria-label="Conversation flow">
              <span>YOUR QUESTION</span><span className="flow-arrow" aria-hidden="true">→</span>
              <span>ARIA</span><span className="flow-arrow" aria-hidden="true">→</span>
              <span>SUPPORT ANSWER</span>
            </div>
            <ul className="auth-points">
              <li>Check fictional demo orders and delivery status</li>
              <li>Try Aura&apos;s return, cancellation, and shipping policies</li>
              <li>Review the transcript and structured summary after a call</li>
            </ul>
          </section>

          <section className="auth-form-panel" aria-labelledby="login-title">
            <p className="eyebrow">EVALUATOR SIGN IN</p>
            <h2 id="login-title">Continue to the demo</h2>
            <p className="subtle">Use the verified evaluator account supplied by the project owner. Public sign-up is disabled.</p>
            {linkError && <p role="alert" className="notice error">That sign-in link is invalid or expired. Sign in with your evaluator password.</p>}
            <form className="login-form" onSubmit={submit}>
              <label className="field">Email<input type="email" required autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
              <label className="field">Password<input type="password" required autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
              <button className="button primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}<span aria-hidden="true">→</span></button>
            </form>
            <button type="button" className="button magic-link" disabled={busy || !email} onClick={magicLink}>Email me a sign-in link</button>
            <p className="auth-footnote">Magic links use Supabase&apos;s built-in sender and currently work only for project team addresses. No external SMTP is configured.</p>
            {message && <p role="status" className="notice auth-message">{message}</p>}
          </section>
        </div>
      </div>
    </main>
  );
}
