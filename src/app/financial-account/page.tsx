// src/app/financial-account/page.tsx
"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

import {
  getMe,
  getBalance,
  getInvoices,
  getPaymentHistory,
  getScholarships,
  getPaymentConfig,
  startCheckout,
  confirmCheckout,
  type MeResponse,
} from "@/lib/api";
import { normalizeErrorMessage, isAbortError, formatDate } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import ErrorBanner from "@/components/ErrorBanner";
import EmptyState from "@/components/EmptyState";
import { FinancialSkeleton } from "@/components/LoadingSkeleton";
import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import PageContainer from "@/components/layout/PageContainer";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";

/* ─── Page-specific constants ─── */

const PAY_METHODS_LS_KEY = "aiu_payment_methods_v1";

/* ─── Page-specific types ─── */

type PaymentMethod = {
  id: string;
  brand: "VISA" | "MASTERCARD" | "OTHER";
  last4: string;
  expiryMonth: string;
  expiryYear: string;
  cardholderName: string;
  email?: string;
  isDefault: boolean;
  createdAt: string;
};

type FinancialPageData = {
  student?: { student_id: string; name: string };
  account: {
    term: string;
    currency: string;
    current_balance: number;
    payment_due_date: string;
    payment_status: string;
    total_charges: number;
    transportation_fee: number;
    tuition_fee: number;
    fines: number;
    scholarship_credit: number;
    payments_made: number;
  };
  transactions: Array<{
    date: string;
    description: string;
    category: string;
    type: string;
    amount: number;
    currency: string;
    status: string;
  }>;
  scholarships: Array<{
    type: string;
    percentage: number;
    amount: number;
    status: string;
    criteria_basis: string;
  }>;
  payment_methods_source: "frontend_local_storage";
};

/* ─── Page-specific utility functions ─── */

function formatMoney(amount: number, currency: string) {
  try {
    return `${amount.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${currency}`;
  } catch {
    return `${amount} ${currency}`;
  }
}

function maskCardNumber(last4: string) {
  if (!last4) return "••••";
  return `•••• •••• •••• ${last4}`;
}

function safeParseJson<T>(s: string | null, fallback: T): T {
  try {
    if (!s) return fallback;
    return JSON.parse(s) as T;
  } catch {
    return fallback;
  }
}

function loadPaymentMethods(): PaymentMethod[] {
  if (typeof window === "undefined") return [];
  const raw = localStorage.getItem(PAY_METHODS_LS_KEY);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const parsed = safeParseJson<any[]>(raw, []);
  // Migrate old format: convert full cardNumber → last4, strip cvv
  const methods: PaymentMethod[] = parsed.map((m) => {
    if (m.cardNumber && !m.last4) {
      const digits = (m.cardNumber as string).replace(/\s+/g, "");
      m.last4 = digits.slice(-4);
      delete m.cardNumber;
    }
    delete m.cvv;
    return m as PaymentMethod;
  });
  let hasDefault = methods.some((m) => m.isDefault);
  if (!hasDefault && methods.length) {
    methods[0].isDefault = true;
  }
  if (methods.length) savePaymentMethods(methods);
  return methods;
}

function savePaymentMethods(methods: PaymentMethod[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(PAY_METHODS_LS_KEY, JSON.stringify(methods));
  } catch {}
}

async function fetchFinancialPage(
  token: string,
  me: MeResponse,
  transactionsLimit = 5,
): Promise<FinancialPageData> {
  const [balance, invoices, payments, scholarships] = await Promise.all([
    getBalance(token),
    getInvoices(token),
    getPaymentHistory(token),
    getScholarships(token),
  ]);

  const currency = balance.currency || "EGP";

  const merged = [
    ...(invoices as any[]).map((t) => ({
      date: t.date,
      description: t.description,
      category: t.category,
      type: t.type,
      amount: t.amount,
      currency: t.currency || currency,
      status: t.status,
    })),
    ...(payments as any[]).map((t) => ({
      date: t.date,
      description: `Payment via ${t.method || "Cash"}`,
      category: t.method || "Payment",
      type: "payment",
      amount: t.amount,
      currency: t.currency || currency,
      status: t.status,
    })),
  ]
    .sort((a, b) => {
      const da = new Date(a.date).getTime() || 0;
      const db = new Date(b.date).getTime() || 0;
      return db - da;
    })
    .slice(0, transactionsLimit);

  return {
    student: { student_id: me.student_number, name: me.full_name },
    account: {
      term: balance.semester ?? "",
      currency,
      current_balance: balance.balance ?? 0,
      payment_due_date: balance.due_date ?? "",
      payment_status: balance.payment_status ?? "",
      total_charges: balance.total_charges ?? 0,
      transportation_fee: balance.transportation_fee ?? 0,
      tuition_fee: balance.tuition_fee ?? 0,
      fines: balance.fines ?? 0,
      scholarship_credit: balance.scholarship_credit ?? 0,
      payments_made: balance.payments_made ?? 0,
    },
    transactions: merged,
    scholarships: (scholarships as any[]).map((s) => ({
      type: s.type,
      percentage: s.percentage,
      amount: s.amount,
      status: s.status,
      criteria_basis: s.criteria_basis,
    })),
    payment_methods_source: "frontend_local_storage",
  };
}

function isOverdue(dueDate: string): boolean {
  if (!dueDate) return false;
  try {
    const due = new Date(dueDate);
    const now = new Date();
    return due < now;
  } catch {
    return false;
  }
}

/* ─── Page component ─── */

export default function FinancialAccountPage() {
  const { t } = useLanguage();
  const { isDark } = useTheme();
  const { token, signOut } = useAuth();

  const [summary, setSummary] = useState<MeResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [financial, setFinancial] = useState<FinancialPageData | null>(null);
  const [loadingFinancial, setLoadingFinancial] = useState(false);
  const [showAllTx, setShowAllTx] = useState(false);

  // Online payment (Stripe test mode)
  const [paymentEnabled, setPaymentEnabled] = useState(false);
  const [starting, setStarting] = useState(false);
  const [payNote, setPayNote] = useState<{ kind: "success" | "info"; text: string } | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const defaultMethod = methods.find((m) => m.isDefault) ?? null;

  // Payment modal
  const [payOpen, setPayOpen] = useState(false);
  const [payBrand, setPayBrand] = useState<"VISA" | "MASTERCARD" | "OTHER">("VISA");
  const [payCardNumber, setPayCardNumber] = useState("");
  const [payExpMonth, setPayExpMonth] = useState("");
  const [payExpYear, setPayExpYear] = useState("");
  const [payCardholder, setPayCardholder] = useState("");
  const [payCvv, setPayCvv] = useState("");
  const [payEmail, setPayEmail] = useState("");
  const [payErrors, setPayErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (typeof window === "undefined") return;
    setMethods(loadPaymentMethods());
  }, []);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();

    setErr(null);
    setLoadingFinancial(true);

    (async () => {
      try {
        const me = await getMe(token, controller.signal);
        if (controller.signal.aborted) return;
        setSummary(me);
        const d = await fetchFinancialPage(token, me, 5);
        if (controller.signal.aborted) return;
        setFinancial(d);
      } catch (e) {
        if (isAbortError(e) || controller.signal.aborted) return;
        const msg = normalizeErrorMessage(e, "Failed to load financial account");
        if (msg.toLowerCase().includes("unauthorized") || msg.toLowerCase().includes("invalid token")) {
          signOut();
          return;
        }
        setErr(msg);
      } finally {
        if (!controller.signal.aborted) setLoadingFinancial(false);
      }
    })();

    return () => controller.abort();
  }, [token, signOut, reloadKey]);

  // Gateway availability + handle the return from Stripe Checkout.
  useEffect(() => {
    if (!token) return;
    let active = true;
    getPaymentConfig(token)
      .then((c) => active && setPaymentEnabled(!!c.enabled))
      .catch(() => {});

    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      if (params.get("canceled")) {
        setPayNote({ kind: "info", text: "Payment canceled — no charge was made." });
        window.history.replaceState({}, "", "/financial-account");
      } else {
        const sid = params.get("session_id");
        if (params.get("paid") && sid) {
          window.history.replaceState({}, "", "/financial-account");
          confirmCheckout(token, sid)
            .then((r) => {
              if (r.paid) {
                setPayNote({
                  kind: "success",
                  text: r.already_recorded
                    ? "Payment already recorded — your balance is up to date."
                    : `✅ Payment successful! ${r.amount ?? ""} EGP paid — new balance ${r.new_balance ?? 0} EGP.`,
                });
                setReloadKey((k) => k + 1);
              } else {
                setPayNote({ kind: "info", text: "Payment was not completed." });
              }
            })
            .catch((e) => setErr(normalizeErrorMessage(e, "Could not confirm payment")));
        }
      }
    }
    return () => {
      active = false;
    };
  }, [token]);

  async function beginStripeCheckout() {
    if (!token) return;
    setErr(null);
    setPayNote(null);
    setStarting(true);
    try {
      const { url } = await startCheckout(token);
      window.location.href = url; // redirect to Stripe's hosted checkout
    } catch (e) {
      setErr(normalizeErrorMessage(e, "Could not start payment"));
      setStarting(false);
    }
  }

  async function viewAllTransactions() {
    if (!token || !summary) return;

    setShowAllTx(true);
    try {
      const d = await fetchFinancialPage(token, summary, 200);
      setFinancial(d);
    } catch (e) {
      setErr(normalizeErrorMessage(e, "Failed to load transactions"));
    }
  }

  function setDefaultMethod(id: string) {
    setMethods((prev) => {
      const next = prev.map((m) => ({ ...m, isDefault: m.id === id }));
      savePaymentMethods(next);
      return next;
    });
  }

  function deleteMethod(id: string) {
    setMethods((prev) => {
      const next = prev.filter((m) => m.id !== id);
      if (next.length && !next.some((m) => m.isDefault)) next[0].isDefault = true;
      savePaymentMethods(next);
      return next;
    });
  }

  function openAddMethod() {
    setPayBrand("VISA");
    setPayCardNumber("");
    setPayExpMonth("");
    setPayExpYear("");
    setPayCardholder(summary?.full_name ?? "");
    setPayCvv("");
    setPayEmail("");
    setPayErrors({});
    setPayOpen(true);
  }

  function validatePaymentForm(): boolean {
    const errors: Record<string, string> = {};

    const cardDigits = payCardNumber.replace(/\s+/g, "");
    if (!cardDigits || cardDigits.length < 13 || cardDigits.length > 19 || !/^\d+$/.test(cardDigits)) {
      errors.cardNumber = "Invalid card number (13-19 digits required)";
    }

    const month = parseInt(payExpMonth);
    if (!payExpMonth || isNaN(month) || month < 1 || month > 12) {
      errors.expMonth = "Invalid month (01-12)";
    }

    const year = parseInt(payExpYear);
    const currentYear = new Date().getFullYear() % 100;
    if (!payExpYear || isNaN(year) || year < currentYear || year > currentYear + 20) {
      errors.expYear = "Invalid year";
    }

    if (!payCardholder || payCardholder.trim().length < 3) {
      errors.cardholder = "Name must be at least 3 characters";
    }

    if (!payCvv || !/^\d{3,4}$/.test(payCvv)) {
      errors.cvv = "CVV must be 3-4 digits";
    }

    if (payEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payEmail)) {
      errors.email = "Invalid email format";
    }

    setPayErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function submitAddMethodAndMockPay() {
    if (!validatePaymentForm()) return;

    const cardDigits = payCardNumber.replace(/\s+/g, "");
    const newMethod: PaymentMethod = {
      id: `pm_${Math.random().toString(16).slice(2)}_${Date.now()}`,
      brand: payBrand,
      last4: cardDigits.slice(-4),
      expiryMonth: payExpMonth.padStart(2, "0"),
      expiryYear: payExpYear,
      cardholderName: payCardholder,
      email: payEmail,
      isDefault: methods.length === 0,
      createdAt: new Date().toISOString(),
    };

    setMethods((prev) => {
      const next = prev.length ? [...prev, newMethod] : [newMethod];
      savePaymentMethods(next);
      return next;
    });

    setPayOpen(false);
  }

  function exportTransactionsPDF() {
    if (typeof window === "undefined") return;

    const transactionContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <title>Transaction History - AIU</title>
        <style>
          @page { margin: 20mm; }
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body {
            font-family: Arial, sans-serif;
            padding: 40px;
            background: white;
          }
          .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 3px solid #1E3A8A;
          }
          .logo-section {
            flex: 1;
          }
          .logo-section img {
            height: 70px;
            width: auto;
          }
          .doc-info {
            text-align: right;
            flex: 1;
          }
          .doc-title {
            font-size: 18px;
            font-weight: bold;
            color: #1E3A8A;
            margin-bottom: 5px;
          }
          .doc-date {
            font-size: 13px;
            color: #666;
          }
          .student-info {
            background: #f5f6fa;
            padding: 20px;
            margin-bottom: 30px;
            border-radius: 8px;
          }
          .info-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #e0e0e0;
          }
          .info-row:last-child { border-bottom: none; }
          .info-label {
            font-weight: bold;
            color: #333;
            font-size: 14px;
          }
          .info-value {
            color: #666;
            font-size: 14px;
          }
          table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
          }
          thead {
            background: #1E3A8A;
            color: white;
          }
          th {
            padding: 14px;
            text-align: left;
            font-weight: bold;
            font-size: 13px;
          }
          th:last-child {
            text-align: right;
          }
          tbody tr {
            border-bottom: 1px solid #e0e0e0;
          }
          tbody tr:hover {
            background: #f5f6fa;
          }
          td {
            padding: 12px 14px;
            font-size: 13px;
          }
          td:first-child {
            color: #666;
          }
          td:nth-child(2) {
            color: #333;
            font-weight: 500;
          }
          td:last-child {
            text-align: right;
            font-weight: bold;
          }
          .credit {
            color: #10b981;
          }
          .debit {
            color: #ef4444;
          }
          .footer {
            margin-top: 50px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
            text-align: center;
            color: #999;
            font-size: 12px;
          }
        </style>
      </head>
      <body>
        <div class="header">
          <div class="logo-section">
            <img src="/aiu-header-logo.svg" alt="AIU Logo" />
          </div>
          <div class="doc-info">
            <div class="doc-title">{t("fin.title")}</div>
            <div class="doc-date">${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</div>
          </div>
        </div>

        <div class="student-info">
          <div class="info-row">
            <span class="info-label">{t("fin.studentName")}</span>
            <span class="info-value">${summary?.full_name || 'N/A'}</span>
          </div>
          <div class="info-row">
            <span class="info-label">{t("fin.studentId")}</span>
            <span class="info-value">${financial?.student?.student_id || 'N/A'}</span>
          </div>
          <div class="info-row">
            <span class="info-label">{t("fin.term")}</span>
            <span class="info-value">${financial?.account?.term || 'N/A'}</span>
          </div>
        </div>

        <table>
          <thead>
            <tr>
              <th>{t("fin.date")}</th>
              <th>{t("fin.desc")}</th>
              <th>{t("fin.amount")}</th>
            </tr>
          </thead>
          <tbody>
            ${(financial?.transactions ?? [])
              .map((t) => {
                const ty = t.type?.toLowerCase();
                const isDebit = ty === "charge" || ty === "fine" || ty === "debit";
                const colorClass = isDebit ? "debit" : "credit";
                const prefix = isDebit ? "−" : "+";
                return `
                  <tr>
                    <td>${formatDate(t.date)}</td>
                    <td>${t.description || "—"}</td>
                    <td class="${colorClass}">${prefix}${formatMoney(t.amount ?? 0, t.currency || financial?.account?.currency || 'EGP')}</td>
                  </tr>
                `;
              })
              .join("")}
          </tbody>
        </table>

        <div class="footer">
          © ${new Date().getFullYear()} Al Alamein International University. All rights reserved.
        </div>
      </body>
      </html>
    `;

    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(transactionContent);
      printWindow.document.close();
      printWindow.focus();
      setTimeout(() => {
        printWindow.print();
        printWindow.close();
      }, 250);
    }
  }

  function printInvoice() {
    if (typeof window === "undefined") return;

    const invoiceContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <title>Invoice - AIU</title>
        <style>
          @page { margin: 20mm; }
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body {
            font-family: Arial, sans-serif;
            padding: 40px;
            background: white;
          }
          .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 3px solid #1E3A8A;
          }
          .logo-section {
            flex: 1;
          }
          .logo-section img {
            height: 70px;
            width: auto;
          }
          .invoice-info {
            text-align: right;
            flex: 1;
          }
          .invoice-number {
            font-size: 14px;
            color: #666;
            margin-bottom: 5px;
          }
          .invoice-date {
            font-size: 14px;
            color: #666;
          }
          .student-info {
            background: #f5f6fa;
            padding: 20px;
            margin-bottom: 30px;
            border-radius: 8px;
          }
          .info-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #e0e0e0;
          }
          .info-row:last-child { border-bottom: none; }
          .info-label {
            font-weight: bold;
            color: #333;
          }
          .info-value {
            color: #666;
          }
          .amount-section {
            background: #1E3A8A;
            color: white;
            padding: 20px;
            margin: 30px 0;
            border-radius: 8px;
            text-align: center;
          }
          .amount-label {
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 10px;
          }
          .amount-value {
            font-size: 32px;
            font-weight: bold;
          }
          .bank-info {
            background: #f5f6fa;
            padding: 20px;
            margin-top: 30px;
            border-radius: 8px;
          }
          .bank-title {
            font-weight: bold;
            color: #1E3A8A;
            margin-bottom: 15px;
            font-size: 16px;
          }
          .bank-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            color: #666;
          }
          .footer {
            margin-top: 50px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
            text-align: center;
            color: #999;
            font-size: 12px;
          }
          .service-fees {
            margin: 30px 0;
            padding: 20px;
            border: 2px dashed #1E3A8A;
          }
          .service-fees-title {
            font-weight: bold;
            color: #1E3A8A;
            margin-bottom: 10px;
          }
        </style>
      </head>
      <body>
        <div class="header">
          <div class="logo-section">
            <img src="/aiu-header-logo.svg" alt="AIU Logo" />
          </div>
          <div class="invoice-info">
            <div class="invoice-number">Invoice No: SRVF-FALL25-${financial?.student?.student_id || '000000'}</div>
            <div class="invoice-date">Date: ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: '2-digit', day: '2-digit' })}</div>
          </div>
        </div>

        <div class="student-info">
          <div class="info-row">
            <span class="info-label">Student Name (اسم الطالب):</span>
            <span class="info-value">${summary?.full_name || 'N/A'}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Student ID (رقم الطالب):</span>
            <span class="info-value">${financial?.student?.student_id || 'N/A'}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Program (البرنامج):</span>
            <span class="info-value">UAIS</span>
          </div>
          <div class="info-row">
            <span class="info-label">Specialization (التخصص):</span>
            <span class="info-value">UGRD</span>
          </div>
        </div>

        <div class="amount-section">
          <div class="amount-label">Total Amount Due (المبلغ المستحق بالجنيه)</div>
          <div class="amount-value">${financial?.account?.current_balance || 0} ${financial?.account?.currency || 'EGP'}</div>
        </div>

        <div class="bank-info">
          <div class="bank-title">Bank Information (اسم البنك)</div>
          <div class="bank-row">
            <span>Bank Name (اسم البنك):</span>
            <span>National Bank of Egypt (البنك الأهلي المصري)</span>
          </div>
          <div class="bank-row">
            <span>Branch (الفرع):</span>
            <span>El Alamein Branch (فرع العلمين)</span>
          </div>
          <div class="bank-row">
            <span>Account Name (اسم الحساب):</span>
            <span>Al Alamein International University (جامعة العلمين الدولية)</span>
          </div>
          <div class="bank-row">
            <span>Account Number (رقم الحساب):</span>
            <span>00930711803192010017</span>
          </div>
        </div>

        <div class="service-fees">
          <div class="service-fees-title">{t("fin.serviceFees")}</div>
        </div>

        <div class="footer">
          © ${new Date().getFullYear()} Al Alamein International University. All rights reserved.
        </div>
      </body>
      </html>
    `;

    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(invoiceContent);
      printWindow.document.close();
      printWindow.focus();
      setTimeout(() => {
        printWindow.print();
        printWindow.close();
      }, 250);
    }
  }

  const currency = financial?.account?.currency ?? "EGP";
  const currentBalance = financial?.account?.current_balance ?? 0;
  const dueDate = financial?.account?.payment_due_date ?? "";
  const term = financial?.account?.term ?? "—";
  const overdue = isOverdue(dueDate);

  return (
    <AppLayout activePath="/financial-account" userName={summary?.full_name ?? "Loading..."} hideChatbot={payOpen}>
      <PageContainer>
        {err && (
          <ErrorBanner message={err} isDark={isDark} onDismiss={() => setErr(null)} />
        )}

        {payNote && (
          <div
            className={`mb-4 flex items-center justify-between gap-3 rounded-lg px-4 py-3 text-sm ${
              payNote.kind === "success"
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                : "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300"
            }`}
          >
            <span>{payNote.text}</span>
            <button onClick={() => setPayNote(null)} className="opacity-60 hover:opacity-100" type="button">
              ✕
            </button>
          </div>
        )}

        {loadingFinancial && !financial && (
          <FinancialSkeleton isDark={isDark} />
        )}

        {/* Title */}
        <div className="mb-6 flex items-center gap-3">
          <div className={`grid h-10 w-10 place-items-center rounded-xl ${isDark ? "bg-zinc-800" : "bg-white"} shadow-sm`}>
            <Image
              src="/financial.svg"
              alt="financial"
              width={22}
              height={22}
              className={isDark ? "brightness-0 invert" : ""}
            />
          </div>
          <h1 className={`text-[26px] md:text-[32px] font-extrabold ${isDark ? "text-white" : "text-[#111827]"}`}>
            Financial Account
          </h1>
        </div>

        {/* Balance card with Make Payment button */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mb-6">
          <div className={`rounded-2xl ${isDark ? "bg-gradient-to-br from-[#1E3A8A] to-[#1e40af]" : "bg-[#1E3A8A]"} px-6 py-5 shadow-lg`}>
            <div className="grid grid-cols-1 md:grid-cols-3 items-center gap-4">
              <div className="text-white/90 font-semibold text-sm">{t("fin.balance")}</div>

              <div className="text-center">
                <motion.div
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: 0.3, type: "spring", stiffness: 200, damping: 15 }}
                  className="text-white text-[22px] md:text-[26px] font-extrabold"
                >
                  {loadingFinancial ? "Loading..." : formatMoney(currentBalance, currency)}
                </motion.div>
                <div className="mt-1 flex items-center justify-center gap-2 text-white/80 text-xs">
                  <span className="inline-block">{overdue ? "⚠️" : "📅"}</span>
                  <span>
                    Payment {overdue ? "Overdue" : "Due"}: {formatDate(dueDate)}
                  </span>
                </div>
                {overdue && (
                  <div className="mt-1 text-xs font-bold text-red-300">{t("fin.payNow")}</div>
                )}
              </div>

              <div className="flex flex-col items-stretch gap-1 md:items-end">
                <button
                  onClick={paymentEnabled ? beginStripeCheckout : openAddMethod}
                  disabled={currentBalance === 0 || starting}
                  className={`h-[52px] rounded-full ${
                    currentBalance === 0 || starting
                      ? "bg-white/20 text-white/40 cursor-not-allowed"
                      : "bg-white text-[#1E3A8A] hover:bg-white/90"
                  } px-6 font-bold text-sm transition-colors shadow-lg`}
                  type="button"
                >
                  {starting ? "Redirecting to checkout…" : "Make Payment"}
                </button>
                {paymentEnabled && (
                  <span className="text-center text-[10px] text-white/70 md:text-right">
                    🔒 Secured by Stripe
                  </span>
                )}
              </div>
            </div>
          </div>
        </motion.div>

        {/* Account summary */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <div className={`mb-4 text-sm font-bold ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
            Account Summary – {term}
          </div>
          <div className="mb-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "Total Charges", value: financial?.account?.total_charges ?? 0 },
              { label: "Transportation Payments", value: financial?.account?.transportation_fee ?? 0 },
              { label: "Semester Payments", value: financial?.account?.tuition_fee ?? 0 },
              { label: "Total Fines", value: financial?.account?.fines ?? 0 },
            ].map((c) => (
              <div
                key={c.label}
                className={`rounded-xl ${
                  isDark ? "bg-gradient-to-br from-[#1E3A8A] to-[#1e40af]" : "bg-[#1E3A8A]"
                } px-4 py-4 shadow-sm`}
              >
                <div className="text-white/80 text-xs font-semibold">{c.label}</div>
                <div className="mt-2 text-white text-[18px] font-extrabold">{formatMoney(c.value, currency)}</div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Transaction History */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="mb-8">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Image
                src="/transaction.svg"
                alt="tx"
                width={22}
                height={22}
                className={isDark ? "brightness-0 invert" : ""}
              />
              <div className={`text-[18px] font-extrabold ${isDark ? "text-white" : "text-zinc-900"}`}>
                {t("fin.title")}
              </div>
            </div>
            <Button
              onClick={exportTransactionsPDF}
              className={`h-9 rounded-full px-6 text-xs font-bold ${
                isDark
                  ? "bg-[#1E3A8A] hover:bg-[#193276] text-white"
                  : "bg-[#1E3A8A] hover:bg-[#193276] text-white"
              }`}
              type="button"
            >
              Export PDF
            </Button>
          </div>

          <div className={`rounded-2xl ${isDark ? "bg-zinc-900 border border-zinc-800" : "bg-white border border-zinc-200"} shadow-sm overflow-hidden`}>
            <table className="w-full">
              <thead>
                <tr className={`${isDark ? "bg-zinc-950/40" : "bg-[#F5F6FA]"} border-b ${isDark ? "border-zinc-800" : "border-zinc-200"}`}>
                  <th className={`px-6 py-4 text-left text-[12px] font-bold ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{t("fin.date")}</th>
                  <th className={`px-6 py-4 text-left text-[12px] font-bold ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{t("fin.desc")}</th>
                  <th className={`px-6 py-4 text-right text-[12px] font-bold ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{t("fin.amount")}</th>
                </tr>
              </thead>
              <tbody>
                {!loadingFinancial && (financial?.transactions ?? []).length === 0 && (
                  <tr>
                    <td colSpan={3}>
                      <EmptyState
                        title={t("fin.noTx")}
                        description="Your transaction history will appear here."
                        icon="💳"
                        isDark={isDark}
                      />
                    </td>
                  </tr>
                )}

                {(financial?.transactions ?? []).slice(0, showAllTx ? 200 : 5).map((t, idx) => {
                  // charges/fines are debits the student owes; payments/scholarships are credits
                  const ty = t.type?.toLowerCase();
                  const isDebit = ty === "charge" || ty === "fine" || ty === "debit";
                  const amountClass = isDebit ? "text-red-600" : "text-green-600";
                  const prefix = isDebit ? "−" : "+";
                  return (
                  <tr key={`${t.date}-${idx}`} className={`border-b ${isDark ? "border-zinc-800 hover:bg-zinc-800/50" : "border-zinc-100 hover:bg-zinc-50"} hover:shadow-md transition-shadow duration-200`}>
                      <td className={`px-6 py-4 text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                          {formatDate(t.date)}
                          </td>
                          <td className={`px-6 py-4 text-sm ${isDark ? "text-zinc-100" : "text-zinc-800"}`}>
                              {t.description || "—"}
                              </td>
                              <td className={`px-6 py-4 text-right text-sm font-bold ${amountClass}`}>
                                  {prefix}{formatMoney(t.amount ?? 0, t.currency || currency)}
                                  </td>
                                  </tr>
                                  );
                                  })}
              </tbody>
            </table>

            {(financial?.transactions ?? []).length > 5 && (
              <div className="px-6 py-4 flex justify-center border-t border-zinc-200">
                <Button
                  onClick={() => (showAllTx ? setShowAllTx(false) : viewAllTransactions())}
                  className={`h-10 rounded-full px-8 text-sm font-bold ${
                    isDark
                      ? "bg-[#1E3A8A] hover:bg-[#193276] text-white"
                      : "bg-[#1E3A8A] hover:bg-[#193276] text-white"
                  }`}
                  type="button"
                >
                  {showAllTx ? "View less" : "View all"}
                </Button>
              </div>
            )}
          </div>
        </motion.div>

        {/* Saved Payment Methods */}
        <div className="mb-8">
          <div className="mb-3 flex items-center gap-2">
            <Image
              src="/savedpayment.svg"
              alt="saved"
              width={22}
              height={22}
              className={isDark ? "brightness-0 invert" : ""}
            />
            <div className={`text-[18px] font-extrabold ${isDark ? "text-white" : "text-zinc-900"}`}>
              Saved Payment Methods
            </div>
          </div>

          <div className={`rounded-2xl border ${isDark ? "border-zinc-800 bg-zinc-900" : "border-zinc-200 bg-white"} shadow-sm px-5 py-5`}>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-stretch">
              {/* Default card */}
              <div
                className={`rounded-2xl border-2 ${
                  isDark
                    ? "border-zinc-700 bg-zinc-950/40"
                    : "border-[#1E3A8A] bg-white"
                } p-4`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className={`${isDark ? "text-white" : "text-zinc-900"} font-extrabold text-sm`}>
                      {defaultMethod?.brand ?? "Visa"}
                    </div>
                    <div className={`mt-2 text-sm font-bold ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                      {defaultMethod ? maskCardNumber(defaultMethod.last4) : "No saved card"}
                    </div>
                    <div className={`mt-1 text-xs ${isDark ? "text-zinc-500" : "text-zinc-500"}`}>
                      {summary?.full_name ?? "—"}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-[#1E3A8A] px-3 py-1 text-[10px] font-extrabold text-white">
                      Default
                    </span>
                  </div>
                </div>

                {defaultMethod && (
                  <div className="mt-3 flex items-center justify-between">
                    <div className={`text-xs ${isDark ? "text-zinc-500" : "text-zinc-500"}`}>
                      Exp: {defaultMethod.expiryMonth}/{defaultMethod.expiryYear}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        className={`h-8 rounded-full text-xs font-bold ${
                          isDark ? "border-zinc-700 text-zinc-200 hover:bg-zinc-800" : "border-zinc-200"
                        }`}
                        onClick={() => deleteMethod(defaultMethod.id)}
                        type="button"
                      >
                        Remove
                      </Button>
                    </div>
                  </div>
                )}
              </div>

              {/* Add new method */}
              <button
                onClick={openAddMethod}
                className={`rounded-2xl border-2 border-dashed ${
                  isDark
                    ? "border-zinc-700 bg-zinc-950/40 hover:bg-zinc-950/60"
                    : "border-zinc-200 bg-white hover:bg-zinc-50"
                } transition-colors p-6 flex flex-col items-center justify-center gap-2`}
                type="button"
              >
                <div className={`grid h-10 w-10 place-items-center rounded-xl ${isDark ? "bg-zinc-800" : "bg-zinc-50"}`}>
                  <span className={`text-2xl leading-none ${isDark ? "text-white" : "text-[#1E3A8A]"}`}>+</span>
                </div>
                <div className={`text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                  Add New Payment Method
                </div>
              </button>
            </div>

            <div className="mt-4 flex justify-center">
              <Button
                onClick={printInvoice}
                className={`h-10 rounded-full px-8 text-sm font-bold ${
                  isDark
                    ? "bg-[#1E3A8A] hover:bg-[#193276] text-white"
                    : "bg-[#1E3A8A] hover:bg-[#193276] text-white"
                }`}
                type="button"
              >
                Print Invoice
              </Button>
            </div>

            {/* Other methods */}
            {methods.length > 1 && (
              <div className="mt-5">
                <div className={`text-xs font-bold mb-2 ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                  Other saved methods
                </div>
                <div className="space-y-2">
                  {methods
                    .filter((m) => !m.isDefault)
                    .map((m) => (
                      <div
                        key={m.id}
                        className={`flex items-center justify-between rounded-xl border ${
                          isDark ? "border-zinc-800 bg-zinc-950/30" : "border-zinc-200 bg-white"
                        } px-4 py-3`}
                      >
                        <div>
                          <div className={`${isDark ? "text-zinc-100" : "text-zinc-900"} text-sm font-extrabold`}>
                            {m.brand}
                          </div>
                          <div className={`text-xs ${isDark ? "text-zinc-500" : "text-zinc-500"}`}>
                            {maskCardNumber(m.last4)}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            className={`h-8 rounded-full text-xs font-bold ${
                              isDark ? "border-zinc-700 text-zinc-200 hover:bg-zinc-800" : "border-zinc-200"
                            }`}
                            onClick={() => setDefaultMethod(m.id)}
                            type="button"
                          >
                            Set Default
                          </Button>
                          <Button
                            variant="outline"
                            className={`h-8 rounded-full text-xs font-bold ${
                              isDark ? "border-zinc-700 text-zinc-200 hover:bg-zinc-800" : "border-zinc-200"
                            }`}
                            onClick={() => deleteMethod(m.id)}
                            type="button"
                          >
                            Remove
                          </Button>
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Scholarships */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="mb-10">
          <div className="mb-3 flex items-center gap-2">
            <Image
              src="/scholarship.svg"
              alt="sch"
              width={22}
              height={22}
              className={isDark ? "brightness-0 invert" : ""}
            />
            <div className={`text-[18px] font-extrabold ${isDark ? "text-white" : "text-zinc-900"}`}>
              Scholarships
            </div>
          </div>

          {!loadingFinancial && (financial?.scholarships ?? []).length === 0 && (
            <div
              className={`rounded-2xl border ${
                isDark ? "border-zinc-800 bg-zinc-900" : "border-zinc-200 bg-white"
              } px-5 py-6 text-sm ${isDark ? "text-zinc-400" : "text-zinc-500"}`}
            >
              No scholarships available.
            </div>
          )}

          {(financial?.scholarships ?? []).length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {(financial?.scholarships ?? []).slice(0, 2).map((s, idx) => {
                const isSport = (s.type || "").toLowerCase().includes("sport");
                return (
                  <div
                    key={`${s.type}-${idx}`}
                    className={`rounded-2xl border ${
                      isDark ? "border-zinc-800 bg-zinc-900" : "border-zinc-200 bg-white"
                    } shadow-sm px-5 py-5 hover:shadow-md transition-shadow duration-200`}
                    style={{
                      background: isSport
                        ? isDark
                          ? undefined
                          : "#FFF7D6"
                        : isDark
                        ? undefined
                        : "#E9F8EE",
                    }}
                  >
                    <div className={`text-xs font-extrabold ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                      {s.type}
                    </div>
                    <div className={`mt-2 text-[15px] font-extrabold ${isDark ? "text-white" : "text-zinc-900"}`}>
                      {formatMoney(s.amount ?? 0, currency)} – {s.percentage ?? 0}%
                    </div>
                    <div className={`mt-1 text-xs ${isDark ? "text-zinc-500" : "text-zinc-500"}`}>
                      {s.criteria_basis ? `• ${s.criteria_basis}` : "• Scholarship criteria"}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </motion.div>
      </PageContainer>

      {/* Payment Modal (outside PageContainer, as it's a fixed overlay) */}
      <AnimatePresence>
        {payOpen && (
          <motion.div
            className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onMouseDown={() => setPayOpen(false)}
          >
            <motion.div
              className={`w-full max-w-[860px] rounded-2xl ${isDark ? "bg-zinc-900 text-white" : "bg-white text-zinc-900"} shadow-2xl overflow-hidden`}
              initial={{ y: 30, scale: 0.96, opacity: 0 }}
              animate={{ y: 0, scale: 1, opacity: 1 }}
              exit={{ y: 20, scale: 0.98, opacity: 0 }}
              transition={{ type: "spring", stiffness: 240, damping: 24 }}
              onMouseDown={(e) => e.stopPropagation()}
            >
              <div className={`${isDark ? "bg-zinc-950/40" : "bg-[#F5F6FA]"} px-8 py-7`}>
                <div className={`text-[22px] font-extrabold ${isDark ? "text-white" : "text-zinc-900"}`}>
                  Alamein International University
                </div>
                <div className={`mt-1 text-xs ${isDark ? "text-zinc-500" : "text-zinc-500"}`}>🔒 Secure payment</div>

                <div className="mt-6 space-y-4">
                  <div
                    className={`rounded-2xl ${isDark ? "bg-zinc-900" : "bg-white"} border ${
                      isDark ? "border-zinc-800" : "border-zinc-200"
                    } p-5`}
                  >
                    <div className="text-xs font-extrabold text-[#B8001F]">{t("fin.cardInfo")}</div>

                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 items-end">
                      <div>
                        <div className={`text-xs font-bold mb-2 ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                          Card Number
                        </div>
                        <Input
                          value={payCardNumber}
                          onChange={(e) => {
                            setPayCardNumber(e.target.value);
                            setPayErrors((prev) => ({ ...prev, cardNumber: "" }));
                          }}
                          placeholder="0000 0000 0000 0000"
                          maxLength={19}
                          className={`h-10 rounded-xl ${
                            isDark ? "bg-zinc-800 border-zinc-700 text-white placeholder:text-zinc-600" : "bg-white"
                          } ${payErrors.cardNumber ? "border-red-500" : ""}`}
                        />
                        {payErrors.cardNumber && (
                          <div className="mt-1 text-xs text-red-500">{payErrors.cardNumber}</div>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
  <div className={`text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
    VISA / Mastercard
  </div>
  <div className="ml-auto flex gap-2">
    <button
      type="button"
      className={`h-8 px-4 rounded-full text-xs font-bold border-2 transition-colors ${
        payBrand === "VISA"
          ? "border-[#1E3A8A] bg-[#1E3A8A] text-white"
          : isDark
          ? "border-zinc-700 bg-transparent text-zinc-300 hover:bg-zinc-800"
          : "border-zinc-300 bg-transparent text-zinc-700 hover:bg-zinc-50"
      }`}
      onClick={() => setPayBrand("VISA")}
    >
      VISA
    </button>
    <button
      type="button"
      className={`h-8 px-4 rounded-full text-xs font-bold border-2 transition-colors ${
        payBrand === "MASTERCARD"
          ? "border-[#1E3A8A] bg-[#1E3A8A] text-white"
          : isDark
          ? "border-zinc-700 bg-transparent text-zinc-300 hover:bg-zinc-800"
          : "border-zinc-300 bg-transparent text-zinc-700 hover:bg-zinc-50"
      }`}
      onClick={() => setPayBrand("MASTERCARD")}
    >
      MC
    </button>
  </div>
</div>
                    </div>

                    <div className="mt-4 grid grid-cols-1 md:grid-cols-4 gap-4">
                      <div>
                        <div className={`text-xs font-bold mb-2 ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                          Expiry Month
                        </div>
                        <Input
                          value={payExpMonth}
                          onChange={(e) => {
                            setPayExpMonth(e.target.value);
                            setPayErrors((prev) => ({ ...prev, expMonth: "" }));
                          }}
                          placeholder="MM"
                          maxLength={2}
                          className={`h-10 rounded-xl ${
                            isDark ? "bg-zinc-800 border-zinc-700 text-white placeholder:text-zinc-600" : "bg-white"
                          } ${payErrors.expMonth ? "border-red-500" : ""}`}
                        />
                        {payErrors.expMonth && <div className="mt-1 text-xs text-red-500">{payErrors.expMonth}</div>}
                      </div>
                      <div>
                        <div className={`text-xs font-bold mb-2 ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                          Expiry Year
                        </div>
                        <Input
                          value={payExpYear}
                          onChange={(e) => {
                            setPayExpYear(e.target.value);
                            setPayErrors((prev) => ({ ...prev, expYear: "" }));
                          }}
                          placeholder="YY"
                          maxLength={2}
                          className={`h-10 rounded-xl ${
                            isDark ? "bg-zinc-800 border-zinc-700 text-white placeholder:text-zinc-600" : "bg-white"
                          } ${payErrors.expYear ? "border-red-500" : ""}`}
                        />
                        {payErrors.expYear && <div className="mt-1 text-xs text-red-500">{payErrors.expYear}</div>}
                      </div>
                      <div className="md:col-span-2">
                        <div className={`text-xs font-bold mb-2 ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                          Cardholder Name
                        </div>
                        <Input
                          value={payCardholder}
                          onChange={(e) => {
                            setPayCardholder(e.target.value);
                            setPayErrors((prev) => ({ ...prev, cardholder: "" }));
                          }}
                          placeholder={t("fin.fullName")}
                          className={`h-10 rounded-xl ${
                            isDark ? "bg-zinc-800 border-zinc-700 text-white placeholder:text-zinc-600" : "bg-white"
                          } ${payErrors.cardholder ? "border-red-500" : ""}`}
                        />
                        {payErrors.cardholder && (
                          <div className="mt-1 text-xs text-red-500">{payErrors.cardholder}</div>
                        )}
                      </div>
                    </div>

                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 items-end">
                      <div>
                        <div className={`text-xs font-bold mb-2 ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                          Security Code
                        </div>
                        <Input
                          value={payCvv}
                          onChange={(e) => {
                            setPayCvv(e.target.value);
                            setPayErrors((prev) => ({ ...prev, cvv: "" }));
                          }}
                          placeholder="CVV"
                          maxLength={4}
                          type="password"
                          className={`h-10 rounded-xl ${
                            isDark ? "bg-zinc-800 border-zinc-700 text-white placeholder:text-zinc-600" : "bg-white"
                          } ${payErrors.cvv ? "border-red-500" : ""}`}
                        />
                        <div className={`mt-1 text-[11px] ${isDark ? "text-zinc-500" : "text-zinc-500"}`}>
                          3 digits on back of your card
                        </div>
                        {payErrors.cvv && <div className="mt-1 text-xs text-red-500">{payErrors.cvv}</div>}
                      </div>
                      <div>
                        <div className={`text-xs font-bold mb-2 ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                          Email Address
                        </div>
                        <Input
                          value={payEmail}
                          onChange={(e) => {
                            setPayEmail(e.target.value);
                            setPayErrors((prev) => ({ ...prev, email: "" }));
                          }}
                          placeholder="email@example.com"
                          className={`h-10 rounded-xl ${
                            isDark ? "bg-zinc-800 border-zinc-700 text-white placeholder:text-zinc-600" : "bg-white"
                          } ${payErrors.email ? "border-red-500" : ""}`}
                        />
                        {payErrors.email && <div className="mt-1 text-xs text-red-500">{payErrors.email}</div>}
                      </div>
                    </div>
                  </div>

                  <div
                    className={`rounded-2xl ${isDark ? "bg-zinc-900" : "bg-white"} border ${
                      isDark ? "border-zinc-800" : "border-zinc-200"
                    } p-5`}
                  >
                    <div className="text-xs font-extrabold text-[#B8001F]">{t("fin.orderDetails")}</div>
                    <div className="mt-3 flex items-center justify-between text-sm">
                      <div className={`${isDark ? "text-zinc-300" : "text-zinc-600"}`}>AIU payment online</div>
                      <div className={`text-[14px] font-extrabold ${isDark ? "text-white" : "text-zinc-900"}`}>
                        TOTAL: {formatMoney(currentBalance, currency)}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-3">
                    <Button
                      variant="outline"
                      className={`h-10 rounded-xl px-6 font-bold ${
                        isDark ? "border-zinc-700 text-zinc-200 hover:bg-zinc-800" : "border-zinc-200"
                      }`}
                      onClick={() => setPayOpen(false)}
                      type="button"
                    >
                      Cancel
                    </Button>
                    <Button
                      className="h-10 rounded-xl bg-[#1E3A8A] px-8 font-bold hover:bg-[#193276] text-white"
                      onClick={submitAddMethodAndMockPay}
                      type="button"
                    >
                      Pay Now
                    </Button>
                  </div>

                  <div className="flex items-center justify-end gap-3 pt-2">
                    <div className={`text-[11px] ${isDark ? "text-zinc-500" : "text-zinc-500"}`}>
                      Powered by National Bank of Egypt
                    </div>
                    <div className="relative h-8 w-[180px]">
                      <Image src="/Bank.svg" alt="Bank" fill className="object-contain" />
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </AppLayout>
  );
}
