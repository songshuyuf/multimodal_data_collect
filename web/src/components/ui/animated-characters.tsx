"use client";

import { useState, useEffect, useRef } from "react";

interface PupilProps {
  size?: number;
  maxDistance?: number;
  pupilColor?: string;
  forceLookX?: number;
  forceLookY?: number;
}

export const Pupil = ({
  size = 12,
  maxDistance = 5,
  pupilColor = "black",
  forceLookX,
  forceLookY,
}: PupilProps) => {
  const [mouseX, setMouseX] = useState(0);
  const [mouseY, setMouseY] = useState(0);
  const pupilRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMouseX(e.clientX);
      setMouseY(e.clientY);
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  const calculatePupilPosition = () => {
    if (!pupilRef.current) return { x: 0, y: 0 };
    if (forceLookX !== undefined && forceLookY !== undefined) {
      return { x: forceLookX, y: forceLookY };
    }
    const pupil = pupilRef.current.getBoundingClientRect();
    const pupilCenterX = pupil.left + pupil.width / 2;
    const pupilCenterY = pupil.top + pupil.height / 2;
    const deltaX = mouseX - pupilCenterX;
    const deltaY = mouseY - pupilCenterY;
    const distance = Math.min(Math.sqrt(deltaX ** 2 + deltaY ** 2), maxDistance);
    const angle = Math.atan2(deltaY, deltaX);
    return { x: Math.cos(angle) * distance, y: Math.sin(angle) * distance };
  };

  const pos = calculatePupilPosition();

  return (
    <div
      ref={pupilRef}
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        backgroundColor: pupilColor,
        transform: `translate(${pos.x}px, ${pos.y}px)`,
        transition: "transform 0.1s ease-out",
      }}
    />
  );
};

interface EyeBallProps {
  size?: number;
  pupilSize?: number;
  maxDistance?: number;
  eyeColor?: string;
  pupilColor?: string;
  isBlinking?: boolean;
  forceLookX?: number;
  forceLookY?: number;
}

export const EyeBall = ({
  size = 48,
  pupilSize = 16,
  maxDistance = 10,
  eyeColor = "white",
  pupilColor = "black",
  isBlinking = false,
  forceLookX,
  forceLookY,
}: EyeBallProps) => {
  const [mouseX, setMouseX] = useState(0);
  const [mouseY, setMouseY] = useState(0);
  const eyeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMouseX(e.clientX);
      setMouseY(e.clientY);
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  const calculatePupilPosition = () => {
    if (!eyeRef.current) return { x: 0, y: 0 };
    if (forceLookX !== undefined && forceLookY !== undefined) {
      return { x: forceLookX, y: forceLookY };
    }
    const eye = eyeRef.current.getBoundingClientRect();
    const eyeCenterX = eye.left + eye.width / 2;
    const eyeCenterY = eye.top + eye.height / 2;
    const deltaX = mouseX - eyeCenterX;
    const deltaY = mouseY - eyeCenterY;
    const distance = Math.min(Math.sqrt(deltaX ** 2 + deltaY ** 2), maxDistance);
    const angle = Math.atan2(deltaY, deltaX);
    return { x: Math.cos(angle) * distance, y: Math.sin(angle) * distance };
  };

  const pos = calculatePupilPosition();

  return (
    <div
      ref={eyeRef}
      style={{
        width: size,
        height: isBlinking ? size * 0.15 : size,
        borderRadius: isBlinking ? `${size / 2}px` : "50%",
        backgroundColor: eyeColor,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transition: "height 0.1s ease, border-radius 0.1s ease",
        overflow: "hidden",
      }}
    >
      {!isBlinking && (
        <div
          style={{
            width: pupilSize,
            height: pupilSize,
            borderRadius: "50%",
            backgroundColor: pupilColor,
            transform: `translate(${pos.x}px, ${pos.y}px)`,
            transition: "transform 0.1s ease-out",
          }}
        />
      )}
    </div>
  );
};

interface AnimatedCharactersProps {
  isTyping?: boolean;
  showPassword?: boolean;
  passwordLength?: number;
}

const DROP_KEYFRAMES = `
@keyframes charDrop {
  0% { transform: translateY(-420px) scale(0.8); opacity: 0; }
  35% { opacity: 1; }
  65% { transform: translateY(12px) scale(1.02); }
  80% { transform: translateY(-6px) scale(0.99); }
  90% { transform: translateY(3px) scale(1.005); }
  100% { transform: translateY(0) scale(1); }
}
`;

export function AnimatedCharacters({
  isTyping = false,
  showPassword = false,
  passwordLength = 0,
}: AnimatedCharactersProps) {
  const [mouseX, setMouseX] = useState(0);
  const [mouseY, setMouseY] = useState(0);
  const [isPurpleBlinking, setIsPurpleBlinking] = useState(false);
  const [isBlackBlinking, setIsBlackBlinking] = useState(false);
  const [isLookingAtEachOther, setIsLookingAtEachOther] = useState(false);
  const [isPurplePeeking, setIsPurplePeeking] = useState(false);
  const [hasLanded, setHasLanded] = useState(false);
  const purpleRef = useRef<HTMLDivElement>(null);
  const blackRef = useRef<HTMLDivElement>(null);
  const yellowRef = useRef<HTMLDivElement>(null);
  const orangeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = setTimeout(() => setHasLanded(true), 1400);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMouseX(e.clientX);
      setMouseY(e.clientY);
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  useEffect(() => {
    const getInterval = () => Math.random() * 4000 + 3000;
    const schedule = () => {
      const t = setTimeout(() => {
        setIsPurpleBlinking(true);
        setTimeout(() => { setIsPurpleBlinking(false); schedule(); }, 150);
      }, getInterval());
      return t;
    };
    const t = schedule();
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    const getInterval = () => Math.random() * 4000 + 3000;
    const schedule = () => {
      const t = setTimeout(() => {
        setIsBlackBlinking(true);
        setTimeout(() => { setIsBlackBlinking(false); schedule(); }, 150);
      }, getInterval());
      return t;
    };
    const t = schedule();
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (isTyping) {
      setIsLookingAtEachOther(true);
      const timer = setTimeout(() => setIsLookingAtEachOther(false), 800);
      return () => clearTimeout(timer);
    }
    setIsLookingAtEachOther(false);
  }, [isTyping]);

  useEffect(() => {
    if (passwordLength > 0 && showPassword) {
      const t = setTimeout(() => {
        setIsPurplePeeking(true);
        setTimeout(() => setIsPurplePeeking(false), 800);
      }, Math.random() * 3000 + 2000);
      return () => clearTimeout(t);
    }
    setIsPurplePeeking(false);
  }, [passwordLength, showPassword, isPurplePeeking]);

  const calcPos = (ref: React.RefObject<HTMLDivElement | null>) => {
    if (!ref.current) return { faceX: 0, faceY: 0, bodySkew: 0 };
    const rect = ref.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 3;
    const deltaX = mouseX - centerX;
    const deltaY = mouseY - centerY;
    return {
      faceX: Math.max(-15, Math.min(15, deltaX / 20)),
      faceY: Math.max(-10, Math.min(10, deltaY / 30)),
      bodySkew: Math.max(-6, Math.min(6, -deltaX / 120)),
    };
  };

  const pp = calcPos(purpleRef);
  const bp = calcPos(blackRef);
  const yp = calcPos(yellowRef);
  const op = calcPos(orangeRef);
  const isHiding = passwordLength > 0 && !showPassword;
  const isPeeking = passwordLength > 0 && showPassword;

  const dropStyle = (delay: number): React.CSSProperties => ({
    animation: `charDrop 0.7s cubic-bezier(0.34, 1.56, 0.64, 1) ${delay}s both`,
  });

  return (
    <>
      <style>{DROP_KEYFRAMES}</style>
      <div className="relative w-[420px] h-[380px] mx-auto">
      {/* Purple tall rectangle */}
      <div
        ref={purpleRef}
        className="absolute bottom-0 left-[40px] w-[130px] h-[260px] rounded-t-[65px] bg-purple-500 z-10"
        style={{
          ...(!hasLanded ? dropStyle(0.1) : {}),
          transform: hasLanded
            ? isPeeking
              ? "skewX(0deg)"
              : isTyping || isHiding
              ? `skewX(${(pp.bodySkew || 0) - 12}deg) translateX(40px)`
              : `skewX(${pp.bodySkew || 0}deg)`
            : undefined,
          transformOrigin: "bottom center",
          transition: hasLanded ? "transform 0.3s ease" : undefined,
        }}
      >
        <div
          className="absolute flex gap-[6px]"
          style={{
            left: isPeeking ? "28px" : isLookingAtEachOther ? "70px" : `${58 + pp.faceX}px`,
            top: isPeeking ? "50px" : isLookingAtEachOther ? "85px" : `${55 + pp.faceY}px`,
            transition: "left 0.3s ease, top 0.3s ease",
          }}
        >
          <EyeBall size={22} pupilSize={10} maxDistance={5} isBlinking={isPurpleBlinking}
            forceLookX={isPeeking ? (isPurplePeeking ? 4 : -4) : isLookingAtEachOther ? 3 : undefined}
            forceLookY={isPeeking ? (isPurplePeeking ? 5 : -4) : isLookingAtEachOther ? 4 : undefined}
          />
          <EyeBall size={22} pupilSize={10} maxDistance={5} isBlinking={isPurpleBlinking}
            forceLookX={isPeeking ? (isPurplePeeking ? 4 : -4) : isLookingAtEachOther ? 3 : undefined}
            forceLookY={isPeeking ? (isPurplePeeking ? 5 : -4) : isLookingAtEachOther ? 4 : undefined}
          />
        </div>
      </div>

      {/* Black tall rectangle */}
      <div
        ref={blackRef}
        className="absolute bottom-0 left-[120px] w-[105px] h-[220px] rounded-t-[52px] bg-gray-900 dark:bg-gray-700 z-20"
        style={{
          ...(!hasLanded ? dropStyle(0.25) : {}),
          transform: hasLanded
            ? isPeeking
              ? "skewX(0deg)"
              : isLookingAtEachOther
              ? `skewX(${(bp.bodySkew || 0) * 1.5 + 10}deg) translateX(20px)`
              : isTyping || isHiding
              ? `skewX(${(bp.bodySkew || 0) * 1.5}deg)`
              : `skewX(${bp.bodySkew || 0}deg)`
            : undefined,
          transformOrigin: "bottom center",
          transition: hasLanded ? "transform 0.3s ease" : undefined,
        }}
      >
        <div
          className="absolute flex gap-[6px]"
          style={{
            left: isPeeking ? "16px" : isLookingAtEachOther ? "42px" : `${36 + bp.faceX}px`,
            top: isPeeking ? "38px" : isLookingAtEachOther ? "20px" : `${45 + bp.faceY}px`,
            transition: "left 0.3s ease, top 0.3s ease",
          }}
        >
          <EyeBall size={20} pupilSize={9} maxDistance={5} isBlinking={isBlackBlinking}
            forceLookX={isPeeking ? -4 : isLookingAtEachOther ? 0 : undefined}
            forceLookY={isPeeking ? -4 : isLookingAtEachOther ? -4 : undefined}
          />
          <EyeBall size={20} pupilSize={9} maxDistance={5} isBlinking={isBlackBlinking}
            forceLookX={isPeeking ? -4 : isLookingAtEachOther ? 0 : undefined}
            forceLookY={isPeeking ? -4 : isLookingAtEachOther ? -4 : undefined}
          />
        </div>
      </div>

      {/* Orange semi-circle */}
      <div
        ref={orangeRef}
        className="absolute bottom-0 left-[10px] w-[180px] h-[180px] rounded-t-[90px] bg-orange-400 z-30"
        style={{
          ...(!hasLanded ? dropStyle(0.45) : {}),
          transform: hasLanded
            ? isPeeking ? "skewX(0deg)" : `skewX(${op.bodySkew || 0}deg)`
            : undefined,
          transformOrigin: "bottom center",
          transition: hasLanded ? "transform 0.3s ease" : undefined,
        }}
      >
        <div
          className="absolute flex gap-[10px]"
          style={{
            left: isPeeking ? "65px" : `${110 + (op.faceX || 0)}px`,
            top: isPeeking ? "115px" : `${120 + (op.faceY || 0)}px`,
            transition: "left 0.3s ease, top 0.3s ease",
          }}
        >
          <Pupil size={12} maxDistance={4} forceLookX={isPeeking ? -5 : undefined} forceLookY={isPeeking ? -4 : undefined} />
          <Pupil size={12} maxDistance={4} forceLookX={isPeeking ? -5 : undefined} forceLookY={isPeeking ? -4 : undefined} />
        </div>
      </div>

      {/* Yellow tall rectangle */}
      <div
        ref={yellowRef}
        className="absolute bottom-0 right-[20px] w-[120px] h-[230px] rounded-t-[60px] bg-yellow-400 z-30"
        style={{
          ...(!hasLanded ? dropStyle(0.6) : {}),
          transform: hasLanded
            ? isPeeking ? "skewX(0deg)" : `skewX(${yp.bodySkew || 0}deg)`
            : undefined,
          transformOrigin: "bottom center",
          transition: hasLanded ? "transform 0.3s ease" : undefined,
        }}
      >
        <div
          className="absolute flex gap-[10px]"
          style={{
            left: isPeeking ? "28px" : `${68 + (yp.faceX || 0)}px`,
            top: isPeeking ? "48px" : `${55 + (yp.faceY || 0)}px`,
            transition: "left 0.3s ease, top 0.3s ease",
          }}
        >
          <Pupil size={12} maxDistance={4} forceLookX={isPeeking ? -5 : undefined} forceLookY={isPeeking ? -4 : undefined} />
          <Pupil size={12} maxDistance={4} forceLookX={isPeeking ? -5 : undefined} forceLookY={isPeeking ? -4 : undefined} />
        </div>
        <div
          className="absolute w-[30px] h-[3px] bg-black rounded-full"
          style={{
            left: isPeeking ? "18px" : `${55 + (yp.faceX || 0)}px`,
            top: isPeeking ? "110px" : `${115 + (yp.faceY || 0)}px`,
            transition: "left 0.3s ease, top 0.3s ease",
          }}
        />
      </div>
    </div>
    </>
  );
}
