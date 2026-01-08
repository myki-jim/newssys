import { useState, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Plus, Pencil, Trash2 } from "lucide-react"
import { toast } from "sonner"

interface User {
  id: number
  username: string
  role: string
  is_active: boolean
  office: string | null
  created_at: string
}

interface UserFormData {
  username: string
  password: string
  role: string
  office: string | null
}

export default function UsersPage() {
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [formData, setFormData] = useState<UserFormData>({
    username: "",
    password: "",
    role: "user",
    office: null,
  })

  // 获取当前用户
  const [currentUser, setCurrentUser] = useState<User | null>(null)

  useEffect(() => {
    const userStr = localStorage.getItem("user")
    if (userStr) {
      setCurrentUser(JSON.parse(userStr))
    }
  }, [])

  // 获取用户列表
  const { data: users, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const token = localStorage.getItem("token")
      const res = await fetch("/api/v1/users", {
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await res.json()
      if (!data.success) throw new Error(data.error?.message || "获取用户列表失败")
      return data.data
    },
    enabled: currentUser?.role === "admin",
  })

  // 创建/更新用户
  const saveMutation = useMutation({
    mutationFn: async (data: UserFormData & { id?: number }) => {
      const token = localStorage.getItem("token")
      const url = data.id
        ? `/api/v1/users/${data.id}`
        : "/api/v1/users"
      const method = data.id ? "PUT" : "POST"

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(data),
      })
      return await res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
      setDialogOpen(false)
      setEditingUser(null)
      setFormData({ username: "", password: "", role: "user", office: null })
      alert(data.id ? "用户更新成功" : "用户创建成功")
    },
    onError: (error: any) => {
      alert(error.message || "操作失败")
    },
  })

  // 删除用户
  const deleteMutation = useMutation({
    mutationFn: async (userId: number) => {
      const token = localStorage.getItem("token")
      const res = await fetch(`/api/v1/users/${userId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      })
      return await res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
      alert("用户删除成功")
    },
  })

  const handleEdit = (user: User) => {
    setEditingUser(user)
    setFormData({
      username: user.username,
      password: "",
      role: user.role,
      office: user.office,
    })
    setDialogOpen(true)
  }

  const handleDelete = (user: User) => {
    if (user.id === currentUser?.id) {
      alert("不能删除自己")
      return
    }
    if (confirm(`确定要删除用户 ${user.username} 吗？`)) {
      deleteMutation.mutate(user.id)
    }
  }

  const handleSubmit = () => {
    if (!formData.username) {
      alert("请输入用户名")
      return
    }
    if (!editingUser && !formData.password) {
      alert("请输入密码")
      return
    }
    saveMutation.mutate({ ...formData, id: editingUser?.id })
  }

  const handleLogout = () => {
    localStorage.removeItem("token")
    localStorage.removeItem("user")
    window.location.href = "/login"
  }

  if (currentUser?.role !== "admin") {
    return (
      <div className="flex items-center justify-center h-96">
        <Card className="max-w-md">
          <CardContent className="pt-6 text-center">
            <p className="text-muted-foreground">您没有权限访问此页面</p>
            <Button onClick={handleLogout} className="mt-4">退出登录</Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (isLoading) {
    return <div className="flex items-center justify-center h-96">加载中...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">用户管理</h1>
          <p className="text-muted-foreground">管理系统用户和权限</p>
        </div>
        <div className="flex gap-2">
          <div className="text-sm text-muted-foreground flex items-center gap-2">
            <span>当前用户: {currentUser?.username}</span>
            <span>({currentUser?.office || "Admin"})</span>
          </div>
          <Button variant="outline" onClick={handleLogout}>退出登录</Button>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button onClick={() => {
                setEditingUser(null)
                setFormData({ username: "", password: "", role: "user", office: null })
              }}>
                <Plus className="mr-2 h-4 w-4" />
                添加用户
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{editingUser ? "编辑用户" : "添加用户"}</DialogTitle>
                <DialogDescription>
                  {editingUser ? "修改用户信息" : "创建新的系统用户"}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>用户名</Label>
                  <Input
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    disabled={!!editingUser}
                  />
                </div>
                <div className="space-y-2">
                  <Label>密码{editingUser && " (留空不修改)"}</Label>
                  <Input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder={editingUser ? "留空不修改" : "请输入密码"}
                  />
                </div>
                <div className="space-y-2">
                  <Label>角色</Label>
                  <Select
                    value={formData.role}
                    onValueChange={(v) => setFormData({ ...formData, role: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="user">普通用户</SelectItem>
                      <SelectItem value="admin">管理员</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>办公室</Label>
                  <Input
                    value={formData.office || ""}
                    onChange={(e) => setFormData({ ...formData, office: e.target.value })}
                    placeholder="例如: 办公室001"
                  />
                </div>
                <Button onClick={handleSubmit} className="w-full">
                  {editingUser ? "更新" : "创建"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>用户列表</CardTitle>
          <CardDescription>
            共 {users?.length || 0} 个用户
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>用户名</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>办公室</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users?.map((user: User) => (
                <TableRow key={user.id}>
                  <TableCell>{user.id}</TableCell>
                  <TableCell>{user.username}</TableCell>
                  <TableCell>
                    <Badge variant={user.role === "admin" ? "default" : "secondary"}>
                      {user.role === "admin" ? "管理员" : "普通用户"}
                    </Badge>
                  </TableCell>
                  <TableCell>{user.office || "-"}</TableCell>
                  <TableCell>
                    <Badge variant={user.is_active ? "default" : "destructive"}>
                      {user.is_active ? "启用" : "禁用"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {new Date(user.created_at).toLocaleString("zh-CN")}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleEdit(user)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(user)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
