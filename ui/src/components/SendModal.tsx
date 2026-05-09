import { useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SendModal({ open, onOpenChange }: Props) {
  const [phone, setPhone] = useState("");
  const [sending, setSending] = useState(false);

  const handleSend = () => {
    const digits = phone.replace(/\D/g, "");
    if (digits.length < 10) {
      toast.error("Enter a valid 10-digit US phone number");
      return;
    }
    setSending(true);
    setTimeout(() => {
      setSending(false);
      onOpenChange(false);
      setPhone("");
      toast.success("📱 Demo: Estimate ready to send", {
        description: `In production, this would text a link to ${phone}.`,
      });
    }, 600);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Send to homeowner</DialogTitle>
          <DialogDescription>
            <span className="block">We'll text a link to view this estimate.</span>
            <span className="mt-2 inline-block rounded-md bg-amber-500/10 px-2 py-1 text-xs font-semibold text-amber-600 dark:text-amber-400">
              ⚠️ DEMO MODE — No actual SMS will be sent
            </span>
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 py-2">
          <Label htmlFor="phone">Phone number</Label>
          <Input
            id="phone"
            type="tel"
            placeholder="(555) 123-4567"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            autoFocus
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSend} disabled={sending}>
            {sending ? "Sending…" : "Send SMS"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
