import { postJson } from "./httpClient";
import type { Flow } from "@/types";
import { toBackendFlow } from "@/services/flowSerializationService";

export async function generateFlow(prompt: string): Promise<Flow> {
  return postJson<Flow>("/flows/generate", { prompt });
}

export async function startFlow(flowId: string): Promise<void> {
  await postJson(`/flows/${flowId}/start`);
}

export async function saveFlow(flow: Flow): Promise<void> {
  await postJson("/flows", toBackendFlow(flow));
}

export async function pauseFlow(): Promise<void> {
  await postJson("/flows/pause");
}

export async function resumeFlow(): Promise<void> {
  await postJson("/flows/resume");
}

export async function abortFlow(): Promise<void> {
  await postJson("/flows/abort");
}

export async function finishFlow(): Promise<void> {
  await postJson("/flows/finish");
}
