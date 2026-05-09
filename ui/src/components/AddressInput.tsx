import { useEffect, useRef, useState } from "react";
import { Loader2, MapPin, FlaskConical, AlertCircle } from "lucide-react";
import { loadGooglePlaces } from "@/lib/googlePlaces";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

interface Props {
  onSubmit: (address: string) => void;
  loading?: boolean;
  autoFocus?: boolean;
}

const CALIBRATION_ADDRESSES = [
  "21106 Kenswick Meadows Ct, Humble, TX 77338",
  "5914 Copper Lilly Lane, Spring, TX 77389",
  "122 NW 13th Ave, Cape Coral, FL 33993",
  "14132 Trenton Ave, Orland Park, IL 60462",
  "835 S Cobble Creek, Nixa, MO 65714",
];

const TEST_ADDRESSES = [
  "3561 E 102nd Ct, Thornton, CO 80229",
  "1612 S Canton Ave, Springfield, MO 65802",
  "6310 Laguna Bay Court, Houston, TX 77041",
  "3820 E Rosebrier St, Springfield, MO 65809",
  "1261 20th Street, Newport News, VA 23607",
];

function validateAddress(address: string): { valid: boolean; error?: string } {
  const trimmed = address.trim();
  if (!trimmed) return { valid: false, error: "Address cannot be empty" };

  // Check for basic components: should have numbers (street number)
  if (!/\d/.test(trimmed)) {
    return { valid: false, error: "Address should include a street number" };
  }

  // Check for at least one comma (city/state separation)
  if (!trimmed.includes(",")) {
    return { valid: false, error: "Please enter a complete address with city and state (e.g., 4204 Gallego Circle, Austin, TX 78738)" };
  }

  // Split by comma to check components
  const parts = trimmed.split(",").map(p => p.trim());

  // Need at least 2 parts (street+city, state or street, city+state)
  if (parts.length < 2) {
    return { valid: false, error: "Please include city and state" };
  }

  // Check that last part has at least 2 letters (state code somewhere)
  const lastPart = parts[parts.length - 1];
  if (!/[A-Za-z]{2}/.test(lastPart)) {
    return { valid: false, error: "Please include state (e.g., TX, California, etc.)" };
  }

  return { valid: true };
}

export function AddressInput({ onSubmit, loading, autoFocus }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [value, setValue] = useState("");
  const [placesReady, setPlacesReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined;
    const promise = loadGooglePlaces(apiKey);
    if (!promise || !inputRef.current) return;

    let listener: any = null;
    let autocomplete: any = null;
    let cancelled = false;

    promise
      .then((google) => {
        if (cancelled || !inputRef.current) return;
        autocomplete = new google.maps.places.Autocomplete(inputRef.current, {
          types: ["address"],
          componentRestrictions: { country: "us" },
          fields: ["formatted_address"],
        });
        listener = autocomplete.addListener("place_changed", () => {
          const place = autocomplete.getPlace();
          const addr = place?.formatted_address;
          if (addr) {
            setValue(addr);
            setError(null);
            onSubmit(addr);
          }
        });
        setPlacesReady(true);
      })
      .catch(() => {
        // graceful fallback: plain text input
      });

    return () => {
      cancelled = true;
      if (listener) listener.remove?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = (address: string) => {
    const validation = validateAddress(address);
    if (!validation.valid) {
      setError(validation.error || "Invalid address");
      return;
    }
    setError(null);
    onSubmit(address);
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim()) handleSubmit(value.trim());
      }}
      className="w-full"
    >
      <div className="group relative flex items-center rounded-xl border border-border bg-card shadow-sm transition focus-within:border-primary focus-within:ring-4 focus-within:ring-primary/10">
        <MapPin className="ml-4 h-5 w-5 shrink-0 text-muted-foreground" />
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Enter a property address…"
          autoFocus={autoFocus}
          disabled={loading}
          className="flex-1 bg-transparent px-3 py-4 text-lg text-foreground outline-none placeholder:text-muted-foreground disabled:opacity-60"
        />
        {loading ? (
          <Loader2 className="mr-4 h-5 w-5 animate-spin text-primary" />
        ) : (
          <button
            type="submit"
            className="mr-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:bg-primary-glow"
          >
            Get estimate
          </button>
        )}
      </div>
      {error && (
        <div className="mt-2 flex items-start gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      <div className="mt-3 flex items-center justify-center gap-2 text-sm text-muted-foreground">
        <span>Try a test address:</span>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 gap-1.5 text-xs"
              disabled={loading}
            >
              <FlaskConical className="h-3.5 w-3.5" />
              Select test address
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="center" className="w-80">
            <DropdownMenuLabel>Calibration (with known benchmarks)</DropdownMenuLabel>
            {CALIBRATION_ADDRESSES.map((address, idx) => (
              <DropdownMenuItem
                key={`cal-${idx}`}
                onClick={() => {
                  setValue(address);
                  setError(null);
                  onSubmit(address);
                }}
                className="font-mono text-xs"
              >
                {address}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Test (for submission)</DropdownMenuLabel>
            {TEST_ADDRESSES.map((address, idx) => (
              <DropdownMenuItem
                key={`test-${idx}`}
                onClick={() => {
                  setValue(address);
                  setError(null);
                  onSubmit(address);
                }}
                className="font-mono text-xs"
              >
                {address}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </form>
  );
}
