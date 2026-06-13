export default function CalibratePage() {
  return (
    <main className="min-h-screen bg-[var(--page-bg)]">
      <div className="h-[var(--navbar-h)] bg-white border-b border-black/10" />

      <div className="mx-auto w-full max-w-[var(--container)] px-[var(--px)] py-10">
        <div className="text-2xl font-semibold">Calibration</div>

        <div className="mt-6 grid grid-cols-3 gap-6">
          <div className="h-[140px] rounded-[var(--card-radius)] bg-white border border-[var(--card-border)]" />
          <div className="h-[140px] rounded-[var(--card-radius)] bg-white border border-[var(--card-border)]" />
          <div className="h-[140px] rounded-[var(--card-radius)] bg-white border border-[var(--card-border)]" />
        </div>
      </div>
    </main>
  );
}
