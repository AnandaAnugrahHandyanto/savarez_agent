import { Button } from "@nous-research/ui/ui/components/button";
import { cn } from "@/lib/utils";
import { AlertCircle, FileText, ImageIcon, Loader2, X } from "lucide-react";

import type { ComposerAttachment } from "./attachmentTypes";

interface Props {
  attachments: ComposerAttachment[];
  onRemove?: (id: string) => void;
}

export function ComposerAttachmentList({ attachments, onRemove }: Props) {
  if (attachments.length === 0) return null;

  return (
    <div className="flex max-w-full flex-wrap gap-1.5 px-1 pt-1">
      {attachments.map((attachment) => (
        <AttachmentPill
          key={attachment.id}
          attachment={attachment}
          onRemove={onRemove}
        />
      ))}
    </div>
  );
}

function AttachmentPill({
  attachment,
  onRemove,
}: {
  attachment: ComposerAttachment;
  onRemove?: (id: string) => void;
}) {
  const isUploading = attachment.uploadState === "uploading";
  const hasError = attachment.uploadState === "error";
  const Icon = attachment.kind === "image" ? ImageIcon : FileText;

  return (
    <div
      className={cn(
        "group/attachment relative flex min-w-0 max-w-[12rem] shrink-0 items-center gap-1.5 rounded-md border px-2 py-1 text-xs",
        hasError
          ? "border-destructive/40 bg-destructive/5"
          : "border-border/40 bg-muted/20",
      )}
    >
      {attachment.kind === "image" && attachment.dataUrl ? (
        <img
          src={attachment.dataUrl}
          alt=""
          className="h-8 w-8 shrink-0 rounded object-cover"
        />
      ) : (
        <Icon className="h-3.5 w-3.5 shrink-0 text-text-secondary" />
      )}

      <span className="min-w-0 truncate text-text-secondary">
        {attachment.label}
      </span>

      {isUploading && (
        <Loader2 className="h-3 w-3 shrink-0 animate-spin text-text-tertiary" />
      )}
      {hasError && (
        <AlertCircle
          className="h-3 w-3 shrink-0 text-destructive"
          aria-label="Upload failed"
        />
      )}

      {onRemove && (
        <Button
          type="button"
          ghost
          size="icon"
          className="h-5 w-5 shrink-0 opacity-0 transition group-hover/attachment:opacity-100 focus-visible:opacity-100"
          onClick={() => onRemove(attachment.id)}
          aria-label={`Remove ${attachment.label}`}
        >
          <X className="h-3 w-3" />
        </Button>
      )}
    </div>
  );
}
