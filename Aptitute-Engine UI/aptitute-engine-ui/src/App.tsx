import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom';
import { ConnectionIndicator } from './components/ConnectionIndicator';
import Overview from './pages/Overview';
import TestSetup from './pages/TestSetup';
import TestRunner from './pages/TestRunner';
import TestResult from './pages/TestResult';
import Practice from './pages/Practice';
import FormulasIndex from './pages/FormulasIndex';
import FormulasDetail from './pages/FormulasDetail';
import Admin from './pages/Admin';
import AdminBatches from './pages/Admin/Batches';
import AdminReview from './pages/Admin/Review';
import AdminMetrics from './pages/Admin/Metrics';
import { BlockedPanel } from './components/BlockedPanel';

/** Spec §7.3: the runner and report are bare routes — no nav, no tab bar, so
 *  the user cannot click into Practice mid-test. */
const BARE_ROUTES = ['/test/run', '/test/result'];

function AppShell() {
  const { pathname } = useLocation();
  const bare = BARE_ROUTES.includes(pathname);

  return (
    <div className="min-h-screen bg-white text-gray-900">
      <header className="border-b border-gray-200">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
          <div className="flex items-center space-x-4">
            <span className="text-xl font-semibold">Aptitude Engine</span>
            {!bare && (
              <nav className="hidden md:flex space-x-4">
                <NavLink
                  to="/"
                  end
                  className={({ isActive }) =>
                    isActive
                      ? 'text-indigo-600 font-medium border-b-2 border-indigo-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }
                >
                  Overview
                </NavLink>
                <NavLink
                  to="/test/new"
                  end
                  className={({ isActive }) =>
                    isActive
                      ? 'text-indigo-600 font-medium border-b-2 border-indigo-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }
                >
                  Test
                </NavLink>
                <NavLink
                  to="/practice"
                  end
                  className={({ isActive }) =>
                    isActive
                      ? 'text-indigo-600 font-medium border-b-2 border-indigo-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }
                >
                  Practice
                </NavLink>
                <NavLink
                  to="/formulas"
                  end
                  className={({ isActive }) =>
                    isActive
                      ? 'text-indigo-600 font-medium border-b-2 border-indigo-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }
                >
                  Formulas
                </NavLink>
              </nav>
            )}
          </div>
          <div className="flex items-center">
            <ConnectionIndicator />
          </div>
        </div>
      </header>
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/test/new" element={<TestSetup />} />
          <Route path="/test/run" element={<TestRunner />} />
          <Route path="/test/result" element={<TestResult />} />
          <Route path="/practice" element={<Practice />} />
          <Route path="/formulas" element={<FormulasIndex />} />
          <Route path="/formulas/:chapterKey" element={<FormulasDetail />} />
          <Route path="/admin" element={<Admin />}>
            <Route
              index
              element={
                <BlockedPanel
                  endpoint="POST/GET /api/v1/batches, /api/v1/batches/{id}/review, /api/v1/metrics"
                  contractDoc="docs/API_CONTRACTS.md §1.2–§1.6"
                />
              }
            />
            <Route path="batches" element={<AdminBatches />} />
            <Route path="review" element={<AdminReview />} />
            <Route path="metrics" element={<AdminMetrics />} />
            <Route
              path="*"
              element={<BlockedPanel endpoint="*" contractDoc="docs/API_CONTRACTS.md" />}
            />
          </Route>
          <Route
            path="*"
            element={
              <div className="mx-auto max-w-3xl px-4 py-16 text-center">
                <h1 className="text-xl font-semibold text-gray-900">Page not found</h1>
                <a href="/" className="mt-4 inline-block text-indigo-600 hover:underline">
                  Back to Overview
                </a>
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}

export default App;
