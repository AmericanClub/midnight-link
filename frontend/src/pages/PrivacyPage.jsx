import React from "react";
import { Link } from "react-router-dom";
import LegalLayout from "@/components/LegalLayout";

const UPDATED = "August 2026";

export default function PrivacyPage() {
  return (
    <LegalLayout title="Privacy Policy" updated={UPDATED} testid="privacy-page">
      <p>
        This Privacy Policy explains how Midnight Link ("we", "us", or "our"), a service
        operated from Siak, Indonesia, collects, uses, and protects your
        information when you use midnightlink.link and the Midnight Link service (the "Service"). By using
        the Service you agree to this Policy.
      </p>

      <h2>1. Information we collect</h2>
      <ul>
        <li><strong>Account information:</strong> your name, email address, and password (stored only as a secure hash).</li>
        <li><strong>Workspace &amp; content:</strong> the links, QR codes, destinations, custom domains, and protection rules you create.</li>
        <li><strong>Billing information:</strong> subscription plan and invoices. Payments are handled by third-party payment providers; we do not store your full card or bank details.</li>
        <li><strong>Click &amp; traffic analytics:</strong> when someone visits your links, we record aggregated event data such as country, device, browser, referrer, and risk signals. Visitor IP addresses are used transiently for geo/risk evaluation and are not stored in raw form — a rotating daily hash is used instead of the raw IP.</li>
        <li><strong>Technical data:</strong> cookies and standard log data required to operate and secure the Service.</li>
      </ul>

      <h2>2. How we use information</h2>
      <ul>
        <li>To provide, maintain, and improve the Service;</li>
        <li>To authenticate you and keep your account secure;</li>
        <li>To process subscriptions and payments;</li>
        <li>To generate analytics and traffic-protection decisions for your links;</li>
        <li>To communicate with you about your account, support requests, and important updates;</li>
        <li>To detect, prevent, and address abuse, fraud, and security issues.</li>
      </ul>

      <h2>3. Cookies</h2>
      <p>
        We use strictly necessary cookies to keep you signed in (secure, httpOnly session
        cookies) and to remember preferences such as theme and language. We do not sell your
        data or use it for third-party advertising.
      </p>

      <h2>4. Third-party service providers</h2>
      <p>We share the minimum data necessary with trusted providers, including:</p>
      <ul>
        <li><strong>Payment processors</strong> — to process your subscription payments securely;</li>
        <li><strong>IP-intelligence provider</strong> — visitor IP addresses may be checked against a proxy/VPN detection service to power traffic protection;</li>
        <li><strong>Infrastructure &amp; hosting providers</strong> — to run the Service.</li>
      </ul>
      <p>These providers are only permitted to use your data to perform services on our behalf.</p>

      <h2>5. Data retention</h2>
      <p>
        We retain account and content data for as long as your account is active. Analytics
        events are retained to provide historical reporting and may be aggregated or pruned over
        time. You may request deletion of your account and associated data at any time.
      </p>

      <h2>6. Data security</h2>
      <p>
        We use industry-standard measures to protect your data, including encrypted transport
        (HTTPS), hashed passwords, encrypted storage of sensitive integration keys, and
        role-based access controls. No method of transmission or storage is completely secure,
        but we work to protect your information.
      </p>

      <h2>7. Your rights</h2>
      <ul>
        <li>Access, update, or correct your account information from your settings;</li>
        <li>Request a copy or deletion of your personal data;</li>
        <li>Withdraw consent or object to certain processing, where applicable.</li>
      </ul>
      <p>To exercise these rights, contact us at <a href="mailto:support@midnightlink.link">support@midnightlink.link</a>.</p>

      <h2>8. Children's privacy</h2>
      <p>
        The Service is not directed to children under 18, and we do not knowingly collect data
        from them.
      </p>

      <h2>9. International data</h2>
      <p>
        Your data may be processed on servers located outside your country. Where required, we
        take steps to ensure appropriate protection for such transfers.
      </p>

      <h2>10. Changes to this Policy</h2>
      <p>
        We may update this Policy periodically. Material changes will be communicated through the
        Service or by email, and the "Last updated" date above will be revised.
      </p>

      <h2>11. Contact</h2>
      <p>
        For privacy questions, email <a href="mailto:support@midnightlink.link">support@midnightlink.link</a>{" "}
        or visit our <Link to="/contact">contact page</Link>.
      </p>
    </LegalLayout>
  );
}
