export type Role = "user" | "assistant";

export interface Message {
  id: string;
  role: Role;
  content: string;
  createdAt: string;
}

export interface GenerateRequest {
  prompt: string;
  max_tokens?: number;
  temperature?: number;
}

export interface ChatError {
  message: string;
  status?: number;
}
