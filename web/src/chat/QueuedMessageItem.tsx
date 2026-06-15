import { Button } from "@nous-research/ui/ui/components/button";
import {
  ArrowRight,
  ArrowUp,
  Paperclip,
  Pencil,
  Trash2,
} from "lucide-react";

interface Props {
  text: string;
  attachmentCount?: number;
  onSendNow(): void;
  onEdit(): void;
  onDelete(): void;
}

export function QueuedMessageItem({
  text,
  attachmentCount = 0,
  onSendNow,
  onEdit,
  onDelete,
}: Props) {
  const hasAttachments = attachmentCount > 0;
  const displayText =
    text ||
    (hasAttachments
      ? `${attachmentCount} attachment${attachmentCount === 1 ? "" : "s"}`
      : "");

  return (
    <div className="flex items-center gap-2 px-2 py-1.5">
      <ArrowRight className="h-3.5 w-3.5 shrink-0 text-text-tertiary" />

      {hasAttachments && (
        <span
          className="flex shrink-0 items-center gap-0.5 text-text-tertiary"
          title={`${attachmentCount} attachment(s)`}
        >
          <Paperclip className="h-3 w-3" />
          <span className="text-xs tabular-nums">{attachmentCount}</span>
        </span>
      )}

      <p className="min-w-0 flex-1 truncate text-sm text-text-secondary">
        {displayText}
      </p>

      <div className="flex shrink-0 items-center gap-0.5">
        <Button
          type="button"
          ghost
          size="icon"
          className="h-7 w-7"
          onClick={onSendNow}
          aria-label="Send now"
          title="Send now"
        >
          <ArrowUp className="h-3.5 w-3.5" />
        </Button>
        <Button
          type="button"
          ghost
          size="icon"
          className="h-7 w-7"
          onClick={onEdit}
          aria-label="Edit"
          title="Edit"
        >
          <Pencil className="h-3.5 w-3.5" />
        </Button>
        <Button
          type="button"
          ghost
          size="icon"
          className="h-7 w-7"
          onClick={onDelete}
          aria-label="Delete"
          title="Delete"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
