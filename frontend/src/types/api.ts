export type UserRole = "user" | "admin";

export interface UserProfile {
  id: number;
  email: string;
  role: UserRole;
  balance_credits: number;
  created_at?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string; // "bearer"
}

export type TransactionType = "credit" | "debit";

export interface Transaction {
  id: number;
  user_id: number;
  amount: number;
  type: TransactionType;
  description: string;
  created_at: string;
}

export type PredictionStatus = "pending" | "success" | "failed";

export interface Prediction {
  id: number;
  user_id: number;
  prompt_ru: string;
  prompt_en?: string;
  s3_key?: string;
  public_url?: string;
  credits_spent: number;
  status: PredictionStatus;
  created_at: string;
}

export interface PredictionEnqueueResponse {
  task_id: string;
  cost_credits: number;
  queued: boolean;
  message: string;
}

export interface MLModel {
  id: number;
  name: string;
  display_name: string;
  model_type: "translation" | "image_generation";
  engine: string;
  version: string;
  is_active: boolean;
  cost_credits: number;
  created_at: string;
}