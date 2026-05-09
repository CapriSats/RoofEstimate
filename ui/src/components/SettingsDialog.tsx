import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Settings as SettingsIcon } from "lucide-react";

type SolarMode = "off" | "fusion" | "primary";

interface SettingsResponse {
  solar_mode: SolarMode;
  solar_mode_options: SolarMode[];
  solar_mode_descriptions: Record<SolarMode, string>;
}

const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function SettingsDialog() {
  const [open, setOpen] = useState(false);
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [pending, setPending] = useState<SolarMode | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    fetch(`${apiUrl}/settings`)
      .then((r) => r.json())
      .then((s: SettingsResponse) => {
        setSettings(s);
        setPending(s.solar_mode);
      })
      .catch(() => {
        // backend offline; surface gracefully
        setSettings(null);
      });
  }, [open]);

  async function save() {
    if (!pending) return;
    setSaving(true);
    try {
      await fetch(`${apiUrl}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ solar_mode: pending }),
      });
      setSettings((s) => (s ? { ...s, solar_mode: pending } : s));
      setOpen(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="text-muted-foreground" title="Pipeline settings">
          <SettingsIcon className="h-4 w-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Pipeline settings</DialogTitle>
          <DialogDescription>
            Choose how the roof measurement is computed. Changes apply to the next estimate.
          </DialogDescription>
        </DialogHeader>

        {!settings ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Loading settings…
          </p>
        ) : (
          <RadioGroup
            value={pending ?? settings.solar_mode}
            onValueChange={(v) => setPending(v as SolarMode)}
            className="gap-3"
          >
            {settings.solar_mode_options.map((mode) => (
              <Label
                key={mode}
                htmlFor={`mode-${mode}`}
                className="flex cursor-pointer items-start gap-3 rounded-lg border border-border/60 p-3 hover:bg-accent"
              >
                <RadioGroupItem id={`mode-${mode}`} value={mode} className="mt-1" />
                <div className="flex-1">
                  <div className="font-mono text-sm font-semibold capitalize">{mode}</div>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {settings.solar_mode_descriptions[mode]}
                  </p>
                </div>
              </Label>
            ))}
          </RadioGroup>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setOpen(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={save} disabled={saving || !pending || pending === settings?.solar_mode}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
