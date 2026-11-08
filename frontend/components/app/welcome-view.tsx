'use client';


/* Palette: ink #07110F, panel #0D1A17, line #1E322D, mint #2EE6C5, saffron #FFB347, text #E8F2EF, muted #8CA39D */

const FONT = { fontFamily: 'var(--font-display), var(--font-hindi), system-ui, sans-serif' };

function LogoMark({ className = 'size-9' }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} fill="none" aria-hidden="true">
      <rect width="40" height="40" rx="12" fill="#2EE6C5" />
      <path
        d="M6 21h7l3-8 5 15 4-11 2 4h7"
        stroke="#07110F"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PulseLine() {
  return (
    <svg
      viewBox="0 0 600 80"
      preserveAspectRatio="none"
      className="h-14 w-full"
      fill="none"
      aria-hidden="true"
    >
      <path
        className="aarogya-pulse"
        d="M0 42h150l18-4 14 4h30l14-30 18 62 18-52 12 20h40l16-6 14 6h254"
        stroke="#FFB347"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={1}
      />
    </svg>
  );
}

const DOCTORS = [
  { name: 'Dr. Meera Sharma', hi: 'डॉ. मीरा शर्मा', field: 'General physician', fee: 500 },
  { name: 'Dr. Rahul Verma', hi: 'डॉ. राहुल वर्मा', field: 'Paediatrician', fee: 600 },
  { name: 'Dr. Anjali Gupta', hi: 'डॉ. अंजलि गुप्ता', field: 'Skin specialist', fee: 700 },
  { name: 'Dr. Imran Khan', hi: 'डॉ. इमरान खान', field: 'Dentist', fee: 400 },
];

const STEPS = [
  { title: 'Enter your mobile number', body: 'Type it here, so the agent never has to catch digits by ear.' },
  { title: 'Talk in Hindi', body: 'Book, move or cancel a visit, or ask for a call back from staff.' },
  { title: 'Confirm once', body: 'The agent repeats doctor, day, time and name, and acts only after you agree.' },
];

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
  phone: string;
  onPhoneChange: (value: string) => void;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  phone,
  onPhoneChange,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  const phoneValid = /^[6-9]\d{9}$/.test(phone);
  const showHint = phone.length > 0 && !phoneValid;

  return (
    <div
      ref={ref}
      style={FONT}
      className="relative h-svh overflow-y-auto scroll-smooth bg-[#07110F] text-[#E8F2EF]"
    >
      <style>{`
        .aarogya-pulse{stroke-dasharray:1;stroke-dashoffset:1;animation:aarogya-draw 3.2s ease-in-out infinite}
        @keyframes aarogya-draw{0%{stroke-dashoffset:1}55%,100%{stroke-dashoffset:0}}
        @media (prefers-reduced-motion:reduce){.aarogya-pulse{animation:none;stroke-dashoffset:0}}
      `}</style>

      {/* soft light behind the hero */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[520px] bg-[radial-gradient(60%_80%_at_20%_0%,rgba(46,230,197,0.14),transparent_70%)]"
      />

      {/* Top bar */}
      <div className="sticky top-4 z-20 px-4 md:px-6">
      <header className="mx-auto flex max-w-6xl items-center justify-between rounded-full border border-[#1E322D] bg-[#0D1A17]/85 px-4 py-2.5 backdrop-blur md:px-6">
        <a href="#top" className="flex items-center gap-3">
          <LogoMark />
          <span className="leading-tight">
            <span className="block text-base font-bold tracking-tight">Aarogya Demo Clinic</span>
            <span className="block text-xs text-[#8CA39D]">आरोग्य डेमो क्लिनिक</span>
          </span>
        </a>
        <nav className="flex items-center gap-1 text-sm md:gap-2">
          <a href="#doctors" className="hidden rounded-full px-3 py-2 text-[#8CA39D] transition hover:text-white sm:block">
            Doctors
          </a>
          <a href="#how" className="hidden rounded-full px-3 py-2 text-[#8CA39D] transition hover:text-white sm:block">
            How it works
          </a>
        </nav>
      </header>
      </div>

      <main id="top" className="relative mx-auto max-w-6xl px-5 pt-14 pb-20 md:px-6 md:pt-20">
        {/* Hero */}
        <section className="grid items-center gap-12 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <p className="mb-5 inline-block rounded-2xl border border-[#2EE6C5]/30 bg-[#2EE6C5]/10 px-4 py-1.5 text-sm font-semibold">
              Powered by <span className="text-[#2EE6C5]">Gnani Prisma</span> (speech-to-text) and{' '}
              <span className="text-[#2EE6C5]">Timbre</span> (text-to-speech)
            </p>
            <h1 className="text-4xl leading-[1.08] font-extrabold tracking-tight text-balance md:text-6xl">
              Book your clinic visit by talking.
            </h1>
            <p lang="hi" className="mt-4 text-xl text-[#FFB347] md:text-2xl">
              बोलकर अपॉइंटमेंट बुक कीजिए
            </p>
            <p className="mt-5 max-w-[46ch] text-base leading-relaxed text-[#8CA39D] md:text-lg">
              A Hindi voice receptionist for a demo clinic in Delhi. It books, moves and cancels
              appointments, and passes billing questions to staff.
            </p>

            {/* Start card */}
            <div className="mt-9 max-w-md rounded-3xl border border-[#1E322D] bg-[#0D1A17] p-5 shadow-[0_20px_60px_-30px_rgba(46,230,197,0.35)]">
              <label htmlFor="phone" className="text-sm font-semibold">
                Your mobile number
              </label>
              <div className="mt-2 flex items-center rounded-2xl border border-[#1E322D] bg-[#07110F] transition focus-within:border-[#2EE6C5] focus-within:ring-4 focus-within:ring-[#2EE6C5]/15">
                <span className="pl-4 text-[#8CA39D]">+91</span>
                <input
                  id="phone"
                  type="tel"
                  inputMode="numeric"
                  autoComplete="tel-national"
                  maxLength={10}
                  placeholder="10 digits"
                  value={phone}
                  onChange={(e) => onPhoneChange(e.target.value.replace(/\D/g, '').slice(0, 10))}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && phoneValid) onStartCall();
                  }}
                  aria-invalid={showHint}
                  aria-describedby="phone-help"
                  className="w-full bg-transparent px-3 py-3.5 text-lg tracking-wide outline-hidden placeholder:text-[#4B625C]"
                />
              </div>
              <p
                id="phone-help"
                className={`mt-2 text-xs ${showHint ? 'text-[#FFB347]' : 'text-[#8CA39D]'}`}
              >
                {showHint
                  ? 'Enter 10 digits, starting with 6, 7, 8 or 9.'
                  : 'This is a demo. Use a fake number, not your own.'}
              </p>
              <button
                type="button"
                onClick={onStartCall}
                disabled={!phoneValid}
                className="mt-4 flex w-full items-center justify-center gap-2.5 rounded-2xl bg-[#2EE6C5] py-3.5 text-base font-bold text-[#07110F] transition hover:bg-[#5cf0d6] focus-visible:ring-4 focus-visible:ring-[#2EE6C5]/40 focus-visible:outline-hidden disabled:cursor-not-allowed disabled:bg-[#1E322D] disabled:text-[#5E746E]"
              >
                <svg viewBox="0 0 24 24" className="size-5" fill="none" aria-hidden="true">
                  <path
                    d="M12 3v11m0 0a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Zm-6-3a6 6 0 0 0 12 0M12 17v4"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
                {startButtonText}
              </button>
            </div>
          </div>

          {/* Example call */}
          <aside
            aria-label="Example call"
            className="overflow-hidden rounded-3xl border border-[#1E322D] bg-[#0D1A17]"
          >
            <div className="border-b border-[#1E322D] px-5 pt-4 pb-1">
              <div className="flex items-center justify-between text-sm">
                <span className="font-semibold">Example call</span>
                <span className="flex items-center gap-2 text-[#8CA39D]">
                  <span className="size-2 rounded-full bg-[#2EE6C5]" />
                  Hindi
                </span>
              </div>
              <PulseLine />
            </div>
            <ol lang="hi" className="space-y-3 px-5 py-5 text-[15px] leading-relaxed">
              <li className="flex justify-end">
                <p className="max-w-[80%] rounded-2xl rounded-br-md border border-[#2EE6C5]/30 bg-[#2EE6C5]/10 px-4 py-2.5">
                  मुझे कल का अपॉइंटमेंट चाहिए
                </p>
              </li>
              <li>
                <p className="max-w-[80%] rounded-2xl rounded-bl-md border border-[#1E322D] bg-[#112420] px-4 py-2.5">
                  किस डॉक्टर के लिए अपॉइंटमेंट चाहिए?
                </p>
              </li>
              <li className="flex justify-end">
                <p className="max-w-[80%] rounded-2xl rounded-br-md border border-[#2EE6C5]/30 bg-[#2EE6C5]/10 px-4 py-2.5">
                  डॉक्टर इमरान खान
                </p>
              </li>
              <li>
                <p className="max-w-[80%] rounded-2xl rounded-bl-md border border-[#1E322D] bg-[#112420] px-4 py-2.5">
                  सुबह 11 बजे, या दोपहर 1 बजकर 20 मिनट। कौन सा समय ठीक रहेगा?
                </p>
              </li>
              <li className="pt-1 text-center font-mono text-xs text-[#FFB347]">
                Booked: Dr. Imran Khan, 1:20 PM
              </li>
            </ol>
          </aside>
        </section>

        {/* Doctors */}
        <section id="doctors" className="mt-28 scroll-mt-28">
          <h2 className="text-2xl font-bold tracking-tight md:text-3xl">Our demo doctors</h2>
          <p className="mt-2 text-[#8CA39D]">Made-up people and fees, for this demo only.</p>
          <ul className="mt-8 divide-y divide-[#1E322D] border-y border-[#1E322D]">
            {DOCTORS.map((d) => (
              <li key={d.name} className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 py-5">
                <div>
                  <p className="text-lg font-semibold">{d.name}</p>
                  <p lang="hi" className="text-sm text-[#8CA39D]">
                    {d.hi}
                  </p>
                </div>
                <p className="text-[#8CA39D]">{d.field}</p>
                <p className="min-w-20 text-right font-semibold text-[#2EE6C5]">₹{d.fee}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* How it works */}
        <section id="how" className="mt-28 scroll-mt-28">
          <h2 className="text-2xl font-bold tracking-tight md:text-3xl">How a call works</h2>
          <ol className="mt-8 grid gap-10 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <li key={s.title} className="relative border-l border-[#1E322D] pl-6">
                <span className="absolute top-0 -left-[13px] flex size-6 items-center justify-center rounded-full bg-[#2EE6C5] text-xs font-bold text-[#07110F]">
                  {i + 1}
                </span>
                <h3 className="text-lg font-semibold">{s.title}</h3>
                <p className="mt-2 max-w-[34ch] text-[#8CA39D]">{s.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <footer className="mt-24 border-t border-[#1E322D] pt-6 text-sm text-[#8CA39D]">
          Demo with fake data only. Speech by Gnani Prisma and Timbre, built on LiveKit Agents.
        </footer>
      </main>
    </div>
  );
};