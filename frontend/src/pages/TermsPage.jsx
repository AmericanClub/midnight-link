import React from "react";
import { Link } from "react-router-dom";
import LegalLayout from "@/components/LegalLayout";

const UPDATED = "August 2026";

export default function TermsPage() {
  return (
    <LegalLayout title="Terms of Service" updated={UPDATED} testid="terms-page">
      <p>
        These Terms of Service ("Terms") govern your access to and use of MidGate (the
        "Service"), a link management and traffic-protection platform available at
        midgate.co. MidGate is operated by an independent sole proprietor based in
        Indonesia ("MidGate", "we", "us", or "our"). By creating an account or using the
        Service, you agree to be bound by these Terms. If you do not agree, do not use the
        Service.
      </p>

      <h2>1. The Service</h2>
      <p>
        MidGate provides smart links, dynamic QR codes, click analytics, bot/proxy/VPN
        detection, configurable traffic-protection rules, custom domains, a developer API,
        webhooks, and team workspaces. Features available to you depend on your subscription
        plan.
      </p>

      <h2>2. Accounts</h2>
      <ul>
        <li>You must provide accurate registration information and keep it up to date.</li>
        <li>You are responsible for safeguarding your password and for all activity under your account.</li>
        <li>You must be at least 18 years old, or the age of majority in your jurisdiction, to use the Service.</li>
        <li>You must notify us immediately of any unauthorized use of your account at support@midgate.co.</li>
      </ul>

      <h2>3. Acceptable use</h2>
      <p>You agree not to use the Service to create, host, or redirect to content that:</p>
      <ul>
        <li>is unlawful, fraudulent, deceptive, or infringes the rights of others;</li>
        <li>distributes malware, phishing, scams, or other harmful or malicious material;</li>
        <li>facilitates spam, unsolicited messaging, or deceptive cloaking of destinations;</li>
        <li>contains or links to child sexual abuse material, terrorism, or content that violates applicable law;</li>
        <li>attempts to disrupt, reverse engineer, or gain unauthorized access to the Service or its infrastructure.</li>
      </ul>
      <p>
        MidGate's protection features are intended for anti-abuse and anti-bot purposes only
        and must not be used to cloak, deceive, or evade lawful review. We may suspend or
        terminate accounts and links that violate this section.
      </p>

      <h2>4. Subscriptions, billing &amp; payments</h2>
      <ul>
        <li>Paid plans are billed in advance on a recurring basis (monthly or annually) according to the plan you select on the Pricing page.</li>
        <li>Payments are processed by third-party payment providers (including QRIS and other supported methods). We do not store your full card or bank credentials.</li>
        <li>By subscribing, you authorize the applicable recurring charge until you cancel.</li>
        <li>Prices are stated in Indonesian Rupiah (IDR) unless otherwise indicated and are exclusive of any taxes that may apply.</li>
        <li>We may change plan pricing with reasonable prior notice; changes take effect on your next billing cycle.</li>
      </ul>

      <h2>5. Refunds &amp; cancellation</h2>
      <p>
        You may cancel at any time. Refund eligibility and the cancellation process are
        described in our <Link to="/refund">Refund &amp; Cancellation Policy</Link>, which
        forms part of these Terms.
      </p>

      <h2>6. Intellectual property</h2>
      <p>
        The Service, including its software, design, and branding, is owned by MidGate and
        protected by applicable laws. We grant you a limited, non-exclusive, non-transferable
        right to use the Service in accordance with these Terms. You retain ownership of the
        content and destinations you configure.
      </p>

      <h2>7. Third-party services</h2>
      <p>
        The Service integrates with third-party providers (for example, payment processors and
        IP-intelligence providers). Your use of those services may be subject to their own
        terms. We are not responsible for third-party websites you link to through the Service.
      </p>

      <h2>8. Disclaimers</h2>
      <p>
        The Service is provided "as is" and "as available" without warranties of any kind,
        whether express or implied. We do not warrant that the Service will be uninterrupted,
        error-free, or that traffic-protection features will detect or block all malicious
        traffic.
      </p>

      <h2>9. Limitation of liability</h2>
      <p>
        To the maximum extent permitted by law, MidGate shall not be liable for any indirect,
        incidental, special, or consequential damages, or for loss of profits, revenue, data,
        or goodwill. Our total liability for any claim relating to the Service shall not exceed
        the amount you paid to us in the three (3) months preceding the event giving rise to the
        claim.
      </p>

      <h2>10. Termination</h2>
      <p>
        You may stop using the Service at any time. We may suspend or terminate your access if
        you breach these Terms or if required by law. Upon termination, your right to use the
        Service ceases immediately.
      </p>

      <h2>11. Changes to these Terms</h2>
      <p>
        We may update these Terms from time to time. Material changes will be communicated
        through the Service or by email. Continued use after changes take effect constitutes
        acceptance of the revised Terms.
      </p>

      <h2>12. Governing law</h2>
      <p>
        These Terms are governed by the laws of the Republic of Indonesia, without regard to
        conflict-of-law principles.
      </p>

      <h2>13. Contact</h2>
      <p>
        Questions about these Terms? Email us at{" "}
        <a href="mailto:support@midgate.co">support@midgate.co</a> or use our{" "}
        <Link to="/contact">contact page</Link>.
      </p>
    </LegalLayout>
  );
}
