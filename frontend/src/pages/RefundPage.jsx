import React from "react";
import { Link } from "react-router-dom";
import LegalLayout from "@/components/LegalLayout";

const UPDATED = "August 2026";

export default function RefundPage() {
  return (
    <LegalLayout title="Refund & Cancellation Policy" updated={UPDATED} testid="refund-page">
      <p>
        This Refund &amp; Cancellation Policy explains how subscriptions to MidGate
        (midgate.co) are billed, cancelled, and refunded. MidGate is operated by an independent
        sole proprietor based in Indonesia. This Policy forms part of our{" "}
        <Link to="/terms">Terms of Service</Link>.
      </p>

      <h2>1. Subscriptions &amp; billing</h2>
      <ul>
        <li>Paid plans are billed in advance for each billing cycle (monthly or annually).</li>
        <li>Your subscription renews automatically at the end of each cycle unless you cancel before the renewal date.</li>
        <li>All prices are in Indonesian Rupiah (IDR) unless otherwise stated, exclusive of applicable taxes.</li>
      </ul>

      <h2>2. Cancellation</h2>
      <ul>
        <li>You may cancel your subscription at any time from your account's Billing page or by emailing <a href="mailto:support@midgate.co">support@midgate.co</a>.</li>
        <li>When you cancel, your plan remains active until the end of the current paid billing cycle; it will not renew afterwards.</li>
        <li>After the cycle ends, your workspace is downgraded to the Free plan. Your data is retained subject to Free-plan limits.</li>
      </ul>

      <h2>3. Refund eligibility</h2>
      <ul>
        <li><strong>7-day money-back guarantee:</strong> If you are a first-time subscriber and are not satisfied, you may request a full refund within seven (7) days of your initial payment, provided the account has not been used in a manner that violates our Terms.</li>
        <li><strong>After 7 days:</strong> Payments for the current billing cycle are generally non-refundable. Cancelling stops future charges but does not refund the current cycle.</li>
        <li><strong>Annual plans:</strong> Outside the 7-day window, annual plans are non-refundable for the remainder of the term unless required by applicable law.</li>
        <li>Refunds are issued to the original payment method and typically process within 7–14 business days, depending on your payment provider.</li>
      </ul>

      <h2>4. Non-refundable items</h2>
      <ul>
        <li>Add-ons or usage-based charges that have already been consumed;</li>
        <li>Accounts terminated for violating our <Link to="/terms">Terms of Service</Link> (including abuse, fraud, or illegal use);</li>
        <li>Partial or unused periods after the 7-day window.</li>
      </ul>

      <h2>5. How to request a refund</h2>
      <p>
        Email <a href="mailto:support@midgate.co">support@midgate.co</a> from the email address
        associated with your account, including your invoice number and the reason for your
        request. We will review and respond within a reasonable time.
      </p>

      <h2>6. Chargebacks</h2>
      <p>
        If you believe a charge is incorrect, please contact us first so we can resolve it
        quickly. Initiating a chargeback without contacting us may result in suspension of your
        account while the dispute is investigated.
      </p>

      <h2>7. Contact</h2>
      <p>
        Questions about billing or refunds? Email{" "}
        <a href="mailto:support@midgate.co">support@midgate.co</a> or visit our{" "}
        <Link to="/contact">contact page</Link>.
      </p>
    </LegalLayout>
  );
}
