import React from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { Router, Route, Link, useLocation } from 'wouter';
import { queryClient } from '@/lib/queryClient';
import { Toaster } from '@/components/ui/toaster';
import Dashboard from '@/pages/Dashboard';
import ExpensesList from '@/pages/ExpensesList';
import NewExpense from '@/pages/NewExpense';
import ExpenseDetail from '@/pages/ExpenseDetail';
import { Home, Receipt, Plus, BarChart3, Menu, X } from 'lucide-react';

const Navigation: React.FC = () => {
  const [location] = useLocation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false);

  const isActive = (path: string) => {
    if (path === '/' && location === '/') return true;
    if (path !== '/' && location.startsWith(path)) return true;
    return false;
  };

  const navLinks = [
    { path: '/', label: 'Dashboard', icon: Home },
    { path: '/expenses', label: 'Expenses', icon: Receipt },
    { path: '/expenses/new', label: 'New Expense', icon: Plus },
  ];

  return (
    <nav className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <div className="flex-shrink-0 flex items-center">
              <BarChart3 className="h-8 w-8 text-blue-600 dark:text-blue-400" />
              <span className="ml-2 text-xl font-bold text-gray-900 dark:text-gray-100">
                ExpenseTracker
              </span>
            </div>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-8">
            {navLinks.map(({ path, label, icon: Icon }) => (
              <Link key={path} href={path}>
                <div
                  className={`flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive(path)
                      ? 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20'
                      : 'text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-50 dark:hover:bg-gray-700'
                  }`}
                >
                  <Icon className="h-4 w-4 mr-2" />
                  {label}
                </div>
              </Link>
            ))}
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden flex items-center">
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="p-2 rounded-md text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              {isMobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isMobileMenuOpen && (
          <div className="md:hidden">
            <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
              {navLinks.map(({ path, label, icon: Icon }) => (
                <Link key={path} href={path}>
                  <div
                    className={`flex items-center px-3 py-2 rounded-md text-base font-medium transition-colors ${
                      isActive(path)
                        ? 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20'
                        : 'text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-50 dark:hover:bg-gray-700'
                    }`}
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    <Icon className="h-5 w-5 mr-3" />
                    {label}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
};

const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <Router>
          <Navigation />
          <main className="max-w-7xl mx-auto">
            <Route path="/" component={Dashboard} />
            <Route path="/expenses" component={ExpensesList} />
            <Route path="/expenses/new" component={NewExpense} />
            <Route path="/expenses/:id" component={ExpenseDetail} />
          </main>
        </Router>
        <Toaster />
      </div>
    </QueryClientProvider>
  );
};

export default App;