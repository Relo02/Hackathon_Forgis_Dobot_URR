import { useState, type ReactNode } from "react";
import type { Device, DeviceType } from "@/types";
import {
  BRANDS,
  EMPTY_FORM,
  PANDA_DEFAULT_IP,
  type DeviceFormData,
} from "@/constants/deviceConfig";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface AddDeviceDialogProps {
  trigger: ReactNode;
  onAdd: (device: Device) => void;
}

export function AddDeviceDialog({ trigger, onAdd }: AddDeviceDialogProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<DeviceFormData>(EMPTY_FORM);

  const set = <K extends keyof DeviceFormData>(key: K, value: DeviceFormData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleTypeChange = (value: DeviceType) => {
    setForm((prev) => ({
      ...prev,
      type: value,
      brand: "",
      robotModel: "",
      apiEndpoint: value === "robot" ? prev.apiEndpoint : "",
    }));
  };

  const handleBrandChange = (value: string) => {
    setForm((prev) => ({
      ...prev,
      brand: value,
      robotModel:
        prev.type === "robot" && value === "Franka" ? "Panda" : prev.robotModel,
      apiEndpoint:
        prev.type === "robot" && value === "Franka"
          ? PANDA_DEFAULT_IP
          : prev.apiEndpoint,
    }));
  };

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) setForm(EMPTY_FORM);
  };

  const handleAdd = () => {
    const fallbackIp =
      form.type === "robot" && form.brand === "Franka"
        ? PANDA_DEFAULT_IP
        : "192.168.1.10";
    const newDevice: Device = {
      id: `device-${Date.now()}`,
      name: form.name.trim(),
      vendor: form.brand,
      type: form.type as DeviceType,
      status: "connected",
      ip: form.apiEndpoint.trim() || fallbackIp,
    };
    onAdd(newDevice);
    handleOpenChange(false);
  };

  const canAdd =
    form.type !== "" &&
    form.brand !== "" &&
    form.name.trim().length > 0;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>

      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Device</DialogTitle>
          <DialogDescription>
            Configure a device to connect to this station.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="device-type">Device Type</Label>
            <Select
              value={form.type}
              onValueChange={(v) => handleTypeChange(v as DeviceType)}
            >
              <SelectTrigger id="device-type">
                <SelectValue placeholder="Select type..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="robot">Robot</SelectItem>
                <SelectItem value="camera">Camera</SelectItem>
                <SelectItem value="sensor">Sensor</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="device-brand">Brand</Label>
            <Select
              value={form.brand}
              onValueChange={handleBrandChange}
              disabled={!form.type}
            >
              <SelectTrigger id="device-brand">
                <SelectValue placeholder={form.type ? "Select brand..." : "Select a type first"} />
              </SelectTrigger>
              <SelectContent>
                {form.type &&
                  BRANDS[form.type].map((brand) => (
                    <SelectItem key={brand} value={brand}>
                      {brand}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>

          {form.type === "robot" && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="robot-model">Model</Label>
              <Input
                id="robot-model"
                value={form.robotModel}
                onChange={(e) => set("robotModel", e.target.value)}
                placeholder="e.g. Panda, UR3, UR10e, IRB 120"
              />
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="device-name">Device Name</Label>
            <Input
              id="device-name"
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="e.g. Robot_01, PLC_Main"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="api-endpoint">
              API Endpoint{" "}
              <span className="text-muted-foreground font-normal">(optional)</span>
            </Label>
            <Input
              id="api-endpoint"
              value={form.apiEndpoint}
              onChange={(e) => set("apiEndpoint", e.target.value)}
              placeholder={form.brand === "Franka" ? PANDA_DEFAULT_IP : "e.g. 192.168.1.10"}
              onKeyDown={(e) => e.key === "Enter" && canAdd && handleAdd()}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            disabled={!canAdd}
            onClick={handleAdd}
            className="bg-primary text-primary-foreground hover:bg-primary/80"
          >
            Add Device
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
