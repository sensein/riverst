/**
 * TeacherRoute.tsx
 * Restricts routes to signed-in accounts with the teacher role.
 */

import React from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Button, Result } from "antd";
import { useAuth } from "../contexts/AuthContext";
import { hasRole } from "../utils/roles";
import FullPageLoader from "./FullPageLoader";

interface TeacherRouteProps {
  children: React.ReactNode;
}

const TeacherRoute: React.FC<TeacherRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  if (isLoading) {
    return <FullPageLoader />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!hasRole(user, "teacher")) {
    return (
      <Result
        status="403"
        title="This page is for teachers"
        subTitle="Ask your KIVA administrator to add your email as a teacher."
        extra={
          <Button type="primary" onClick={() => navigate("/")}>
            Go home
          </Button>
        }
      />
    );
  }

  return <>{children}</>;
};

export default TeacherRoute;
