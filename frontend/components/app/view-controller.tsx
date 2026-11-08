'use client';

import { useTheme } from 'next-themes';
import { AnimatePresence, motion } from 'motion/react';
import { useAgent, useSessionContext } from '@livekit/components-react';
import { AgentSessionView_01 } from '@/components/agents-ui/blocks/agent-session-view-01';
import { WelcomeView } from '@/components/app/welcome-view';

const MotionWelcomeView = motion.create(WelcomeView);
const MotionSessionView = motion.create(AgentSessionView_01);

const VIEW_MOTION_PROPS = {
  variants: {
    visible: {
      opacity: 1,
    },
    hidden: {
      opacity: 0,
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.5,
    ease: 'linear',
  },
};

interface ViewControllerProps {
  isVideoInputSupported: boolean;
  phone: string;
  onPhoneChange: (value: string) => void;
}

export function ViewController({
  isVideoInputSupported,
  phone,
  onPhoneChange,
}: ViewControllerProps) {
  const { isConnected, start } = useSessionContext();
  const agent = useAgent();
  const { resolvedTheme } = useTheme();

  return (
    <>
    {isConnected && (
      <div className="pointer-events-none fixed top-4 left-1/2 z-50 -translate-x-1/2 rounded-full border border-[#2EE6C5]/30 bg-[#0D1A17]/90 px-4 py-1.5 text-center text-xs font-semibold text-[#E8F2EF] backdrop-blur md:text-sm">
        Powered by <span className="text-[#2EE6C5]">Gnani Prisma</span> (speech-to-text) and{' '}
        <span className="text-[#2EE6C5]">Timbre</span> (text-to-speech)
      </div>
    )}
    <AnimatePresence mode="wait">
      {/* Welcome view */}
      {!isConnected && (
        <MotionWelcomeView
          key="welcome"
          {...VIEW_MOTION_PROPS}
          startButtonText="Start call"
          onStartCall={start}
          phone={phone}
          onPhoneChange={onPhoneChange}
        />
      )}
      {/* Session view */}
      {isConnected && (
        <MotionSessionView
          key="session-view"
          {...VIEW_MOTION_PROPS}
          preConnectMessage={
            agent.isConnected ? 'Agent is listening, ask it a question' : 'Waiting for agent'
          }
          supportsChatInput={true}
          supportsVideoInput={isVideoInputSupported}
          supportsScreenShare={isVideoInputSupported}
          isPreConnectBufferEnabled={true}
          themeMode={resolvedTheme === 'dark' ? 'dark' : 'light'}
          className="fixed inset-0"
        />
      )}
    </AnimatePresence>
    </>
  );
}