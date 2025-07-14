import { User, Expense, Approval, InsertUser, InsertExpense, InsertApproval, DashboardStats } from '../shared/schema.js';

export interface IStorage {
  // User operations
  createUser(user: InsertUser): Promise<User>;
  getUser(id: string): Promise<User | null>;
  getUserByEmail(email: string): Promise<User | null>;
  getAllUsers(): Promise<User[]>;
  updateUser(id: string, updates: Partial<InsertUser>): Promise<User>;
  
  // Expense operations
  createExpense(expense: InsertExpense): Promise<Expense>;
  getExpense(id: string): Promise<Expense | null>;
  getExpensesByUser(userId: string): Promise<Expense[]>;
  getExpensesByStatus(status: string): Promise<Expense[]>;
  getExpensesByManager(managerId: string): Promise<Expense[]>;
  getAllExpenses(): Promise<Expense[]>;
  updateExpense(id: string, updates: Partial<Expense>): Promise<Expense>;
  
  // Approval operations
  createApproval(approval: InsertApproval): Promise<Approval>;
  getApprovalsByExpense(expenseId: string): Promise<Approval[]>;
  
  // Dashboard stats
  getDashboardStats(userId?: string): Promise<DashboardStats>;
  
  // Export functionality
  getExpensesInDateRange(startDate: string, endDate: string): Promise<Expense[]>;
}

export class MemStorage implements IStorage {
  private users: Map<string, User> = new Map();
  private expenses: Map<string, Expense> = new Map();
  private approvals: Map<string, Approval> = new Map();
  private userIdCounter = 1;
  private expenseIdCounter = 1;
  private approvalIdCounter = 1;

  constructor() {
    // Initialize with sample data
    this.initializeSampleData();
  }

  private initializeSampleData() {
    // Create sample users
    const adminUser: User = {
      id: 'user-1',
      name: 'John Smith',
      email: 'john.smith@company.com',
      role: 'admin',
      department: 'Finance',
    };

    const managerUser: User = {
      id: 'user-2',
      name: 'Sarah Johnson',
      email: 'sarah.johnson@company.com',
      role: 'manager',
      department: 'Engineering',
      managerId: 'user-1',
    };

    const employeeUser: User = {
      id: 'user-3',
      name: 'Mike Davis',
      email: 'mike.davis@company.com',
      role: 'employee',
      department: 'Engineering',
      managerId: 'user-2',
    };

    this.users.set(adminUser.id, adminUser);
    this.users.set(managerUser.id, managerUser);
    this.users.set(employeeUser.id, employeeUser);

    // Create sample expenses
    const sampleExpenses: Expense[] = [
      {
        id: 'exp-1',
        userId: 'user-3',
        title: 'Business Trip to NYC',
        description: 'Flight and hotel for client meeting',
        amount: 1250.00,
        category: 'travel',
        status: 'pending',
        submittedAt: new Date().toISOString(),
      },
      {
        id: 'exp-2',
        userId: 'user-3',
        title: 'Team Lunch',
        description: 'Lunch with development team',
        amount: 85.50,
        category: 'meals',
        status: 'approved',
        submittedAt: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
        approvedAt: new Date().toISOString(),
        approvedBy: 'user-2',
      },
      {
        id: 'exp-3',
        userId: 'user-2',
        title: 'Office Supplies',
        description: 'Whiteboard markers and sticky notes',
        amount: 45.30,
        category: 'office',
        status: 'approved',
        submittedAt: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
        approvedAt: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
        approvedBy: 'user-1',
      },
    ];

    sampleExpenses.forEach(expense => {
      this.expenses.set(expense.id, expense);
    });

    this.userIdCounter = 4;
    this.expenseIdCounter = 4;
  }

  async createUser(user: InsertUser): Promise<User> {
    const id = `user-${this.userIdCounter++}`;
    const newUser: User = { id, ...user };
    this.users.set(id, newUser);
    return newUser;
  }

  async getUser(id: string): Promise<User | null> {
    return this.users.get(id) || null;
  }

  async getUserByEmail(email: string): Promise<User | null> {
    for (const user of this.users.values()) {
      if (user.email === email) {
        return user;
      }
    }
    return null;
  }

  async getAllUsers(): Promise<User[]> {
    return Array.from(this.users.values());
  }

  async updateUser(id: string, updates: Partial<InsertUser>): Promise<User> {
    const user = this.users.get(id);
    if (!user) {
      throw new Error('User not found');
    }
    const updatedUser = { ...user, ...updates };
    this.users.set(id, updatedUser);
    return updatedUser;
  }

  async createExpense(expense: InsertExpense): Promise<Expense> {
    const id = `exp-${this.expenseIdCounter++}`;
    const newExpense: Expense = {
      id,
      ...expense,
      submittedAt: new Date().toISOString(),
    };
    this.expenses.set(id, newExpense);
    return newExpense;
  }

  async getExpense(id: string): Promise<Expense | null> {
    return this.expenses.get(id) || null;
  }

  async getExpensesByUser(userId: string): Promise<Expense[]> {
    return Array.from(this.expenses.values()).filter(expense => expense.userId === userId);
  }

  async getExpensesByStatus(status: string): Promise<Expense[]> {
    return Array.from(this.expenses.values()).filter(expense => expense.status === status);
  }

  async getExpensesByManager(managerId: string): Promise<Expense[]> {
    const subordinates = Array.from(this.users.values()).filter(user => user.managerId === managerId);
    const subordinateIds = subordinates.map(user => user.id);
    
    return Array.from(this.expenses.values()).filter(expense => 
      subordinateIds.includes(expense.userId) && expense.status === 'pending'
    );
  }

  async getAllExpenses(): Promise<Expense[]> {
    return Array.from(this.expenses.values());
  }

  async updateExpense(id: string, updates: Partial<Expense>): Promise<Expense> {
    const expense = this.expenses.get(id);
    if (!expense) {
      throw new Error('Expense not found');
    }
    const updatedExpense = { ...expense, ...updates };
    this.expenses.set(id, updatedExpense);
    return updatedExpense;
  }

  async createApproval(approval: InsertApproval): Promise<Approval> {
    const id = `approval-${this.approvalIdCounter++}`;
    const newApproval: Approval = {
      id,
      ...approval,
      timestamp: new Date().toISOString(),
    };
    this.approvals.set(id, newApproval);
    return newApproval;
  }

  async getApprovalsByExpense(expenseId: string): Promise<Approval[]> {
    return Array.from(this.approvals.values()).filter(approval => approval.expenseId === expenseId);
  }

  async getDashboardStats(userId?: string): Promise<DashboardStats> {
    const expenses = userId 
      ? Array.from(this.expenses.values()).filter(expense => expense.userId === userId)
      : Array.from(this.expenses.values());

    const currentMonth = new Date().getMonth();
    const currentYear = new Date().getFullYear();

    const monthlyExpenses = expenses.filter(expense => {
      const expenseDate = new Date(expense.submittedAt);
      return expenseDate.getMonth() === currentMonth && expenseDate.getFullYear() === currentYear;
    });

    return {
      totalExpenses: expenses.length,
      pendingApprovals: expenses.filter(expense => expense.status === 'pending').length,
      approvedAmount: expenses
        .filter(expense => expense.status === 'approved')
        .reduce((sum, expense) => sum + expense.amount, 0),
      rejectedCount: expenses.filter(expense => expense.status === 'rejected').length,
      monthlyTotal: monthlyExpenses.reduce((sum, expense) => sum + expense.amount, 0),
    };
  }

  async getExpensesInDateRange(startDate: string, endDate: string): Promise<Expense[]> {
    const start = new Date(startDate);
    const end = new Date(endDate);
    
    return Array.from(this.expenses.values()).filter(expense => {
      const expenseDate = new Date(expense.submittedAt);
      return expenseDate >= start && expenseDate <= end;
    });
  }
}

export const storage = new MemStorage();