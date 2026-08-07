import type { AuthApiUser } from '@/types/auth';

type DemoAccount = {
  email: string;
  password: string;
  token: string;
  user: AuthApiUser;
};

export const DEMO_ACCOUNTS: DemoAccount[] = [
  {
    email: 'sysadmin@wathiq.demo',
    password: '123456',
    token: 'demo-system-admin-token',
    user: {
      id: 'demo-system-admin',
      name: 'System Admin Demo',
      email: 'sysadmin@wathiq.demo',
      role: 'SystemAdmin',
      institutionId: 'inst-demo-1',
      departmentId: 'dept-admin',
      department: 'Administration',
    },
  },
  {
    email: 'institutionadmin@wathiq.demo',
    password: '123456',
    token: 'demo-institution-admin-token',
    user: {
      id: 'demo-institution-admin',
      name: 'Institution Admin Demo',
      email: 'institutionadmin@wathiq.demo',
      role: 'InstitutionAdmin',
      institutionId: 'inst-demo-1',
      departmentId: 'dept-admin',
      department: 'Administration',
    },
  },
  {
    email: 'manager@wathiq.demo',
    password: '123456',
    token: 'demo-manager-token',
    user: {
      id: 'demo-manager',
      name: 'Manager Demo',
      email: 'manager@wathiq.demo',
      role: 'Manager',
      institutionId: 'inst-demo-1',
      departmentId: 'dept-ops',
      department: 'Operations',
    },
  },
  {
    email: 'employee@wathiq.demo',
    password: '123456',
    token: 'demo-employee-token',
    user: {
      id: 'demo-employee',
      name: 'Employee Demo',
      email: 'employee@wathiq.demo',
      role: 'Employee',
      institutionId: 'inst-demo-1',
      departmentId: 'dept-ops',
      department: 'Operations',
    },
  },
];

export function isDemoAuthEnabled(): boolean {
  return import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEMO_AUTH === "true";
}

export function isDemoToken(token: string | null | undefined): boolean {
  return typeof token === "string" && token.startsWith("demo-");
}

export function tryDemoLogin(email: string, password: string): DemoAccount | null {
  if (!isDemoAuthEnabled()) {
    return null;
  }

  const normalizedEmail = email.trim().toLowerCase();

  return (
    DEMO_ACCOUNTS.find(
      (account) =>
        account.email.toLowerCase() === normalizedEmail && account.password === password,
    ) ?? null
  );
}
