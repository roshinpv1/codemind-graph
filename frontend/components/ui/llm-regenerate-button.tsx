"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export type LlmRegenerateVisibility = "always" | "missing" | "placeholder";

interface LlmRegenerateButtonProps {
  onRegenerate: () => Promise<unknown>;
  onSuccess?: () => void;
  onError?: (message: string) => void;
  label?: string;
  pendingLabel?: string;
  regenerateLabel?: string;
  variant?: "outline" | "default" | "ghost";
  size?: "sm" | "default" | "lg" | "icon";
  className?: string;
  visibility?: LlmRegenerateVisibility;
  hasContent?: boolean;
  isPlaceholder?: boolean;
  disabled?: boolean;
}

export function LlmRegenerateButton({
  onRegenerate,
  onSuccess,
  onError,
  label = "Generate",
  pendingLabel = "Generating…",
  regenerateLabel = "Regenerate",
  variant = "outline",
  size = "sm",
  className,
  visibility = "always",
  hasContent = false,
  isPlaceholder = false,
  disabled = false,
}: LlmRegenerateButtonProps) {
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: onRegenerate,
    onSuccess: () => {
      setError(null);
      onSuccess?.();
    },
    onError: (err: Error) => {
      const msg = err.message || "Generation failed";
      setError(msg);
      onError?.(msg);
    },
  });

  const show =
    visibility === "always" ||
    (visibility === "missing" && !hasContent) ||
    (visibility === "placeholder" && (!hasContent || isPlaceholder));

  if (!show) return null;

  const text = mutation.isPending
    ? pendingLabel
    : hasContent && !isPlaceholder
      ? regenerateLabel
      : label;

  return (
    <div className={className}>
      <Button
        type="button"
        variant={variant}
        size={size}
        onClick={() => mutation.mutate()}
        disabled={disabled || mutation.isPending}
      >
        <RefreshCw className={`h-4 w-4 mr-1 ${mutation.isPending ? "animate-spin" : ""}`} />
        {text}
      </Button>
      {error && <p className="text-xs text-destructive mt-1 max-w-xs">{error}</p>}
    </div>
  );
}
