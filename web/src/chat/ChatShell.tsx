interface Props {
  children: React.ReactNode;
}

export function ChatShell({ children }: Props) {
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      {children}
    </div>
  );
}
