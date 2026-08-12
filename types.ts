export enum UserRole {
  ADMIN = 'ADMIN',
  USER = 'USER',
}

export interface UserProfile {
  id: string;
  name: string;
  department: string;
  avatarUrl: string;
  companyName: string;
  role: UserRole;
  team?: string;
  position?: string;
  phone?: string;
  email?: string;
  englishName?: string;
  extensionNumber?: string;
}
