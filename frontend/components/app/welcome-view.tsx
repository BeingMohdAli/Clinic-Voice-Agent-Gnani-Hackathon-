'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { createClient } from '@/lib/supabase/client';

function WelcomeImage() {
  return (
    <svg
      width="64"
      height="64"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="text-[#00dfc4] mb-4 size-16"
    >
      <path
        d="M15 24V40C15 40.7957 14.6839 41.5587 14.1213 42.1213C13.5587 42.6839 12.7956 43 12 43C11.2044 43 10.4413 42.6839 9.87868 42.1213C9.31607 41.5587 9 40.7957 9 40V24C9 23.2044 9.31607 22.4413 9.87868 21.8787C10.4413 21.3161 11.2044 21 12 21C12.7956 21 13.5587 21.3161 14.1213 21.8787C14.6839 22.4413 15 23.2044 15 24ZM22 5C21.2044 5 20.4413 5.31607 19.8787 5.87868C19.3161 6.44129 19 7.20435 19 8V56C19 56.7957 19.3161 57.5587 19.8787 58.1213C20.4413 58.6839 21.2044 59 22 59C22.7956 59 23.5587 58.6839 24.1213 58.1213C24.6839 57.5587 25 56.7957 25 56V8C25 7.20435 24.6839 6.44129 24.1213 5.87868C23.5587 5.31607 22.7956 5 22 5ZM32 13C31.2044 13 30.4413 13.3161 29.8787 13.8787C29.3161 14.4413 29 15.2044 29 16V48C29 48.7957 29.3161 49.5587 29.8787 50.1213C30.4413 50.6839 31.2044 51 32 51C32.7956 51 33.5587 50.6839 34.1213 50.1213C34.6839 49.5587 35 48.7957 35 48V16C35 15.2044 34.6839 14.4413 34.1213 13.8787C33.5587 13.3161 32.7956 13 32 13ZM42 21C41.2043 21 40.4413 21.3161 39.8787 21.8787C39.3161 22.4413 39 23.2044 39 24V40C39 40.7957 39.3161 41.5587 39.8787 42.1213C40.4413 42.6839 41.2043 43 42 43C42.7957 43 43.5587 42.6839 44.1213 42.1213C44.6839 41.5587 45 40.7957 45 40V24C45 23.2044 44.6839 22.4413 44.1213 21.8787C43.5587 21.3161 42.7957 21 42 21ZM52 17C51.2043 17 50.4413 17.3161 49.8787 17.8787C49.3161 18.4413 49 19.2044 49 20V44C49 44.7957 49.3161 45.5587 49.8787 46.1213C50.4413 46.6839 51.2043 47 52 47C52.7957 47 53.5587 46.6839 54.1213 46.1213C54.6839 45.5587 55 44.7957 55 44V20C55 19.2044 54.6839 18.4413 54.1213 17.8787C53.5587 17.3161 52.7957 17 52 17Z"
        fill="currentColor"
      />
    </svg>
  );
}

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
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const phoneValid = /^[6-9]\d{9}$/.test(phone);

  useEffect(() => {
    async function loadUser() {
      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();
        if (user) {
          setUserEmail(user.email ?? null);
          const metaPhone = user.user_metadata?.phone;
          if (metaPhone && !phone) {
            onPhoneChange(metaPhone);
          }
        }
      } catch {
        // Ignore offline / unauthenticated states
      }
    }
    loadUser();
  }, []);

  return (
    <div ref={ref}>
      <section className="bg-background flex flex-col items-center justify-center text-center">
        <WelcomeImage />

        <p className="text-foreground max-w-prose pt-1 leading-6 font-medium">
          Sir Ganga Ram City Hospital: book an appointment by voice
        </p>

        {userEmail ? (
          <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-[#00dfc4]/30 bg-[#00dfc4]/10 px-3.5 py-1 text-xs text-[#00dfc4]">
            <span>
              Signed in as <strong className="text-white">{userEmail}</strong>
            </span>
            <span>•</span>
            <Link href="/signup" className="underline hover:text-white">
              Account
            </Link>
          </div>
        ) : (
          <div className="mt-3">
            <Link
              href="/signup"
              className="inline-flex items-center gap-1.5 rounded-full border border-[#00dfc4]/30 bg-[#00dfc4]/15 px-3.5 py-1 text-xs font-semibold text-[#00dfc4] hover:bg-[#00dfc4]/25 hover:text-white transition"
            >
              <span>Patient Sign In / Sign Up</span>
              <span>→</span>
            </Link>
          </div>
        )}

        <input
          type="tel"
          inputMode="numeric"
          maxLength={10}
          placeholder="Mobile number (10 digits)"
          value={phone}
          onChange={(e) => onPhoneChange(e.target.value.replace(/\D/g, '').slice(0, 10))}
          className="border-input bg-background mt-5 w-64 rounded-full border px-4 py-2 text-center text-sm focus:border-[#00dfc4] focus:ring-2 focus:ring-[#00dfc4]/20 outline-hidden transition"
        />

        <Button
          size="lg"
          onClick={onStartCall}
          disabled={!phoneValid}
          className="mt-3 w-64 rounded-full bg-[#00dfc4] hover:bg-[#00f3d6] text-[#04201c] font-mono text-xs font-bold tracking-wider uppercase shadow-md shadow-[#00dfc4]/20 transition"
        >
          {startButtonText}
        </Button>
      </section>

      <div className="fixed bottom-5 left-0 flex w-full items-center justify-center">
        <p className="text-muted-foreground max-w-prose pt-1 text-xs leading-5 font-normal text-pretty md:text-sm">
          Need help getting set up? Check out the{' '}
          <a
            target="_blank"
            rel="noopener noreferrer"
            href="https://docs.livekit.io/agents/start/voice-ai/"
            className="underline"
          >
            Voice AI quickstart
          </a>
          .
        </p>
      </div>
    </div>
  );
};
