import React, { useEffect, useState } from "react";
import {
  adminGetUsers,
  adminGetTransactions,
  adminGetPredictions,
  adminChangeUserBalance,
} from "../api/client";
import type { UserProfile, Transaction, Prediction } from "../types/api";

type Tab = "users" | "transactions" | "predictions";

export const AdminPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>("users");
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (currentTab: Tab) => {
    setLoading(true);
    setError(null);
    try {
      if (currentTab === "users") {
        setUsers(await adminGetUsers());
      } else if (currentTab === "transactions") {
        setTransactions(await adminGetTransactions());
      } else {
        setPredictions(await adminGetPredictions());
      }
    } catch (e: any) {
      setError(e?.message || "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(tab);
  }, [tab]);

  const handleChangeBalance = async (user: UserProfile) => {
    const amountStr = prompt(
      `На сколько кредитов изменить баланс пользователя ${user.email}? (положительное число = пополнение)`,
      "10",
    );
    if (!amountStr) return;

    const amount = Number(amountStr);
    if (!Number.isFinite(amount) || amount <= 0) return;

    try {
      const updated = await adminChangeUserBalance({
        user_id: user.id,
        amount,
        description: "Admin change via UI",
      });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (e: any) {
      alert(e?.message || "Ошибка изменения баланса");
    }
  };

  return (
    <div className="admin-page">
      <h1>Админка Tortodelova</h1>

      <div className="admin-tabs">
        <button
          className={tab === "users" ? "active" : ""}
          onClick={() => setTab("users")}
        >
          Пользователи
        </button>
        <button
          className={tab === "transactions" ? "active" : ""}
          onClick={() => setTab("transactions")}
        >
          Транзакции
        </button>
        <button
          className={tab === "predictions" ? "active" : ""}
          onClick={() => setTab("predictions")}
        >
          Предсказания
        </button>
      </div>

      {loading && <div>Загрузка...</div>}
      {error && <div className="admin-error">{error}</div>}

      {!loading && tab === "users" && (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Email</th>
                <th>Роль</th>
                <th>Баланс</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.id}</td>
                  <td>{u.email}</td>
                  <td>{u.role}</td>
                  <td>{u.balance_credits}</td>
                  <td>
                    <button
                      className="btn-secondary"
                      onClick={() => handleChangeBalance(u)}
                    >
                      Изменить баланс
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && tab === "transactions" && (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>User ID</th>
                <th>Тип</th>
                <th>Сумма</th>
                <th>Описание</th>
                <th>Дата</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t) => (
                <tr key={t.id}>
                  <td>{t.id}</td>
                  <td>{t.user_id}</td>
                  <td>{t.type}</td>
                  <td>{t.amount}</td>
                  <td>{t.description}</td>
                  <td>{new Date(t.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && tab === "predictions" && (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>User ID</th>
                <th>Статус</th>
                <th>Кредиты</th>
                <th>Промпт (RU)</th>
                <th>Дата</th>
              </tr>
            </thead>
            <tbody>
              {predictions.map((p) => (
                <tr key={p.id}>
                  <td>{p.id}</td>
                  <td>{p.user_id}</td>
                  <td>{p.status}</td>
                  <td>{p.credits_spent}</td>
                  <td>{p.prompt_ru}</td>
                  <td>{new Date(p.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};