"use client";

import { motion } from "framer-motion";
import Image from "next/image";

type Props = {
  size?: number;
  isDark?: boolean;
};

export default function FloatingAIU3D({ size = 90, isDark = false }: Props) {
  const thickness = size * 0.12;
  const radius = size * 0.42;
  // Generate side edge segments for the coin/disc
  const edgeSegments = 40;
  const edges = Array.from({ length: edgeSegments }, (_, i) => {
    const angle = (i / edgeSegments) * Math.PI * 2;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;
    return { x, y, angle };
  });

  return (
    <div
      className="relative flex items-center justify-center"
      style={{
        width: size,
        height: size,
        perspective: "600px",
      }}
    >
      {/* Soft glow */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.3,
          height: size * 1.3,
          background: "radial-gradient(circle, rgba(184,0,31,0.25) 0%, transparent 70%)",
          filter: "blur(12px)",
        }}
        animate={{ scale: [1, 1.15, 1], opacity: [0.5, 0.8, 0.5] }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* 3D rotating container */}
      <motion.div
        style={{
          transformStyle: "preserve-3d",
          width: size,
          height: size,
        }}
        animate={{
          rotateY: [0, 360],
          y: [0, -5, 0],
        }}
        transition={{
          rotateY: { duration: 8, repeat: Infinity, ease: "linear" },
          y: { duration: 3, repeat: Infinity, ease: "easeInOut" },
        }}
        className="relative flex items-center justify-center"
      >
        {/* Back face */}
        <div
          className="absolute rounded-full"
          style={{
            width: radius * 2,
            height: radius * 2,
            background: "linear-gradient(135deg, #8a0017 0%, #B8001F 50%, #a0001a 100%)",
            transform: `translateZ(${-thickness / 2}px) rotateY(180deg)`,
            backfaceVisibility: "hidden",
          }}
        />

        {/* Side edge — individual segments forming the rim */}
        {edges.map((edge, i) => (
          <div
            key={i}
            className="absolute"
            style={{
              width: 3,
              height: thickness,
              background: "linear-gradient(180deg, #d4002a, #B8001F, #8a0017)",
              transform: `translate3d(${edge.x}px, ${edge.y}px, 0px) rotateY(${(edge.angle * 180) / Math.PI + 90}deg)`,
              transformOrigin: "center center",
            }}
          />
        ))}

        {/* Front face */}
        <div
          className="absolute rounded-full flex items-center justify-center"
          style={{
            width: radius * 2,
            height: radius * 2,
            background: isDark
              ? "linear-gradient(145deg, #d4002a 0%, #B8001F 50%, #9a001a 100%)"
              : "linear-gradient(145deg, #e6002e 0%, #B8001F 40%, #a0001a 100%)",
            transform: `translateZ(${thickness / 2}px)`,
            backfaceVisibility: "hidden",
            boxShadow: "inset 0 2px 4px rgba(255,255,255,0.2), inset 0 -2px 4px rgba(0,0,0,0.15)",
          }}
        >
          {/* Brain icon */}
          <div className="relative" style={{ width: radius * 1.2, height: radius * 1.2 }}>
            <Image
              src="/brain.svg"
              alt="AI advisor"
              fill
              className="object-contain"
              style={{ filter: "brightness(0) invert(1) drop-shadow(0 1px 2px rgba(0,0,0,0.2))" }}
            />
          </div>

          {/* AIU text */}
          <span
            className="absolute select-none"
            style={{
              bottom: radius * 0.15,
              fontSize: size * 0.13,
              fontWeight: 800,
              letterSpacing: "0.1em",
              color: "rgba(255,255,255,0.9)",
              textShadow: "0 1px 2px rgba(0,0,0,0.2)",
            }}
          >
            AIU
          </span>
        </div>

        {/* Shine on front face */}
        <div
          className="absolute rounded-full overflow-hidden pointer-events-none"
          style={{
            width: radius * 2,
            height: radius * 2,
            transform: `translateZ(${thickness / 2 + 0.5}px)`,
            backfaceVisibility: "hidden",
          }}
        >
          <div
            style={{
              position: "absolute",
              top: "-20%",
              left: "-20%",
              width: "80%",
              height: "60%",
              background: "radial-gradient(ellipse, rgba(255,255,255,0.2) 0%, transparent 70%)",
              transform: "rotate(-30deg)",
            }}
          />
        </div>

        {/* Green circle indicator */}
        <motion.div
          className="absolute z-10"
          style={{
            bottom: size * 0.08,
            right: size * 0.08,
            width: size * 0.2,
            height: size * 0.2,
            transform: `translateZ(${thickness / 2 + 2}px)`,
          }}
          animate={{ scale: [1, 1.15, 1] }}
          transition={{ duration: 2, repeat: Infinity }}
        >
          <Image src="/greencircle.svg" alt="online" fill className="object-contain drop-shadow-md" />
          <motion.div
            className="absolute inset-0 rounded-full bg-green-400"
            animate={{ scale: [1, 1.5, 1], opacity: [0.4, 0, 0.4] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
        </motion.div>
      </motion.div>
    </div>
  );
}
