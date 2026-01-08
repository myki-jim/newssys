import { Routes, Route, Navigate } from "react-router-dom"
import { MainLayout } from "./components/layouts/MainLayout"
import { DashboardPage } from "./pages/DashboardPage"
import { SourcesPage } from "./pages/SourcesPage"
import { SitemapsPage } from "./pages/SitemapsPage"
import { ArticlesPage } from "./pages/ArticlesPage"
import { ArticleDetailPage } from "./pages/ArticleDetailPage"
import { ReportsPage } from "./pages/ReportsPage"
import { ReportDetailPage } from "./pages/ReportDetailPage"
import { TemplatesPage } from "./pages/TemplatesPage"
import { SearchPage } from "./pages/SearchPage"
import { TasksPage } from "./pages/TasksPage"
import { ChatPage } from "./pages/ChatPage"
import SchedulesPage from "./pages/SchedulesPage"
import SettingsPage from "./pages/SettingsPage"
import TwitterSearchPage from "./pages/TwitterSearchPage"
import GoogleSearchPage from "./pages/GoogleSearchPage"
import SocialMediaSearchPage from "./pages/SocialMediaSearchPage"
import OsintToolsPage from "./pages/OsintToolsPage"
import LoginPage from "./pages/LoginPage"
import UsersPage from "./pages/UsersPage"

function ProtectedRoute({ children }: { children: React.ReactElement }) {
  const token = localStorage.getItem("token")
  if (!token) {
    return <Navigate to="/login" replace />
  }
  return children
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={
        <ProtectedRoute>
          <MainLayout />
        </ProtectedRoute>
      }>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="sources" element={<SourcesPage />} />
        <Route path="sitemaps" element={<SitemapsPage />} />
        <Route path="articles" element={<ArticlesPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="templates" element={<TemplatesPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="schedules" element={<SchedulesPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="twitter-search" element={<TwitterSearchPage />} />
        <Route path="google-search" element={<GoogleSearchPage />} />
        <Route path="social-search" element={<SocialMediaSearchPage />} />
        <Route path="osint" element={<OsintToolsPage />} />
      </Route>
      {/* 详情页面（独立页面，不在 MainLayout 内） */}
      <Route path="/articles/:articleId" element={<ArticleDetailPage />} />
      <Route path="/reports/:reportId" element={<ReportDetailPage />} />
    </Routes>
  )
}

export default App
