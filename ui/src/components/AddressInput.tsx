import { useEffect, useRef, useState } from "react";
import { Loader2, MapPin, FlaskConical } from "lucide-react";
import { loadGooglePlaces } from "@/lib/googlePlaces";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

interface Props {
  onSubmit: (address: string) => void;
  loading?: boolean;
  autoFocus?: boolean;
}

const TEST_ADDRESSES = [
  "3561 E 102nd Ct, Thornton, CO 80229",
  "1612 S Canton Ave, Springfield, MO 65802",
  "6310 Laguna Bay Court, Houston, TX 77041",
  "3820 E Rosebrier St, Springfield, MO 65809",
];

export function AddressInput({ onSubmit, loading, autoFocus }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [value, setValue] = useState("");
  const [placesReady, setPlacesReady] = useState(false);

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

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim()) onSubmit(value.trim());
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
            {TEST_ADDRESSES.map((address, idx) => (
              <DropdownMenuItem
                key={idx}
                onClick={() => {
                  setValue(address);
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
