import { useEffect, useState } from "react";
import type { NodeCreatorState } from "@/types";
import {
  NODE_TYPES,
  TASKS,
  MOTION_TYPES,
  EMPTY_CREATOR,
} from "@/constants/executorConfig";
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
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface NodeCreatorDialogProps {
  open: boolean;
  onClose: () => void;
  onAdd?: (creator: NodeCreatorState) => void;
}

export function NodeCreatorDialog({ open, onClose, onAdd }: NodeCreatorDialogProps) {
  const [creator, setCreator] = useState<NodeCreatorState>(EMPTY_CREATOR);
  const isRobotMotion = creator.nodeType === "robot_action";
  const canCreate = creator.label.trim().length > 0 && (!isRobotMotion || !!creator.motionType);

  // Reset creator form when panel opens
  useEffect(() => {
    if (open) setCreator(EMPTY_CREATOR);
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New Node</DialogTitle>
          <DialogDescription>
            Configure a new node to add to the flow.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="node-type">Node Type</Label>
            <Select
              value={creator.nodeType ?? ""}
              onValueChange={(v) => setCreator({ nodeType: v, task: null, motionType: null, label: "" })}
            >
              <SelectTrigger id="node-type">
                <SelectValue placeholder="Select type..." />
              </SelectTrigger>
              <SelectContent>
                {NODE_TYPES.map((nt) => (
                  <SelectItem key={nt.value} value={nt.value}>{nt.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isRobotMotion ? (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="motion-type">Motion Type</Label>
              <Select
                value={creator.motionType ?? ""}
                onValueChange={(v) =>
                  setCreator((prev) => ({
                    ...prev,
                    motionType: v as "joint" | "linear" | "grasping",
                    label:
                      prev.label ||
                      (v === "joint"
                        ? "Joint Move"
                        : v === "linear"
                          ? "Linear Move"
                          : "Grasping"),
                  }))
                }
              >
                <SelectTrigger id="motion-type">
                  <SelectValue placeholder="Select motion..." />
                </SelectTrigger>
                <SelectContent>
                  {MOTION_TYPES.map((motion) => (
                    <SelectItem key={motion.value} value={motion.value}>{motion.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : creator.nodeType ? (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="node-task">Task</Label>
              <Select
                value={creator.task ?? ""}
                onValueChange={(v) => setCreator((prev) => ({ ...prev, task: v, label: "" }))}
              >
                <SelectTrigger id="node-task">
                  <SelectValue placeholder="Select task..." />
                </SelectTrigger>
                <SelectContent>
                  {TASKS.map((t) => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}

          {(creator.task || creator.motionType) && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="node-label">Label</Label>
              <Input
                id="node-label"
                placeholder={isRobotMotion ? "e.g. Move to Fixture" : "Enter node label..."}
                value={creator.label}
                onChange={(e) => setCreator((prev) => ({ ...prev, label: e.target.value }))}
              />
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={!canCreate}
            onClick={() => { onAdd?.(creator); onClose(); }}
            className="bg-primary text-primary-foreground hover:bg-primary/80"
          >
            Create Node
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
