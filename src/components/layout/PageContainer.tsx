"use client";

type PageContainerProps = {
  children: React.ReactNode;
  className?: string;
};

export default function PageContainer({ children, className = "" }: PageContainerProps) {
  return (
    <main className={`relative min-h-[calc(100vh-300px)] px-4 md:px-8 lg:px-16 py-8 md:py-16 ${className}`}>
      {children}
    </main>
  );
}
