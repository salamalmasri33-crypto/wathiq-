import type { DocumentPriority, DocumentStatus } from "@/types/document";
import type { BackendRole, UserRole } from "@/types/user";

export type AddDocumentForm = {
  title?: string;
  file: File;
  targetUserId?: string | null;
  enableOcr?: boolean;
  priority?: DocumentPriority | null;
  isSensitive?: boolean;
};

export type UpdateDocumentForm = {
  title?: string;
  file?: File;
  priority?: DocumentPriority | null;
  isSensitive?: boolean | null;
};

export type UpsertMetadataDto = {
  description?: string | null;
  broadGenre?: string | null;
  specificGenre?: string | null;
  tags?: string[] | null;
  department?: string | null;
  departmentId?: string | null;
  documentType?: string | null;
  expirationDate?: string | null;
  issuingEntity?: string | null;
  referenceNumber?: string | null;
  documentDate?: string | null;
  insights?: string[] | null;
  hasSignature?: boolean;
  signatures?: string[] | null;
  headers?: string[] | null;
  footers?: string[] | null;
  stamps?: string[] | null;
  rawExtractionJson?: string | null;
};

export type SearchDocumentsDto = {
  query?: string | null;
  institutionId?: string | null;
  broadGenre?: string | null;
  specificGenre?: string | null;
  department?: string | null;
  departmentId?: string | null;
  status?: DocumentStatus | null;
  priority?: DocumentPriority | null;
  fromDate?: string | null;
  toDate?: string | null;
  sortBy?: string | null;
  desc?: boolean | null;
  page?: number | null;
  pageSize?: number | null;
};

export type TransferDocumentDto = {
  targetDepartmentId: string;
  justification: string;
};

export type ReviewDecisionDto = {
  comment: string;
};

export type AddUserDto = {
  name: string;
  email: string;
  password: string;
  role: UserRole | BackendRole;
  institutionId?: string | null;
  departmentId?: string | null;
  department?: string | null;
};

export type UpdateUserDto = {
  name?: string | null;
  email?: string | null;
  newPassword?: string | null;
  institutionId?: string | null;
  departmentId?: string | null;
  department?: string | null;
};
