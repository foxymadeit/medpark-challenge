import { NavLink } from "react-router-dom";

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-logo">M</div>

        <div>
          <div className="brand-title">Secure MOM</div>
          <div className="brand-subtitle">ON-PREMISE AI</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavLink
          to="/meetings"
          className={({ isActive }) =>
            isActive ? "nav-item active" : "nav-item"
          }
        >
          <span className="nav-icon">D</span>
          Meetings
        </NavLink>

        <NavLink
          to="/new-meeting"
          className={({ isActive }) =>
            isActive ? "nav-item active" : "nav-item"
          }
        >
          <span className="nav-icon">+</span>
          New Meeting
        </NavLink>

        <NavLink
          to="/history"
          className={({ isActive }) =>
            isActive ? "nav-item active" : "nav-item"
          }
        >
          <span className="nav-icon">H</span>
          History
        </NavLink>
      </nav>
    </aside>
  );
}

export default Sidebar;
