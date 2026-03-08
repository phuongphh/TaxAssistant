# Issue #6

[Feature] TaxAssistant Portal - User & Growth Metrics Dashboard

## Overview
Build **TaxAssistant Portal** - a web-based admin/business dashboard platform. The first feature of this portal will display user growth metrics and customer segmentation data. This portal will serve as a centralized hub for monitoring, analytics, and future configuration features.

## Portal Purpose
TaxAssistant Portal is a dedicated web application designed to:
- Monitor business metrics and product performance
- Manage customer data and analytics
- Configure system settings and features (future phases)
- Track product usage and growth trends

## Phase 1: User & Growth Metrics Dashboard

### 1. User Growth Metrics
- **Total Active Users**: Count of all active users in the system
- **New User Acquisition**:
  - New users by day
  - New users by month
  - New users by year
- **Growth Trends**: Line/bar chart visualization showing user growth over time

### 2. User Activity Metrics
- **Daily Active Users (DAU)**: Users with at least one activity per day
- **Monthly Active Users (MAU)**: Users with at least one activity per month
- **Activity Trends**: Charts showing activity patterns by day/month/year

### 3. Customer Segmentation
- **User count breakdown by customer type**:
  - Household (Hộ gia đình)
  - Business/Enterprise (Doanh nghiệp)
  - Individual/Self-employed (Cá thể kinh doanh)
- **Visualization**: Pie chart or bar chart showing distribution by type
- **Filter capability**: Ability to view metrics for each customer segment separately

### 4. Data Source & Database Queries
- Query existing customer database tables:
  -  table (user_id, user_type, created_at, user_name)
  -  or  table (user_id, activity_timestamp, activity_type)
  - Ensure efficient queries with proper indexing on , , 
- Aggregate data at hourly intervals for dashboard refresh
- Store hourly snapshots for historical trend analysis

### 5. Technical Requirements
- **Web Application Stack**: Choose appropriate tech stack (React, Vue, Django, FastAPI, etc.)
- **Authentication**: Implement login/access control for portal users
- Dashboard updates every hour
- Responsive design (desktop & mobile)
- Fast loading (< 3 seconds)
- Export capability (CSV format)
- Data accuracy verified against database
- Portal should be scalable for future features (monitoring, configuration, etc.)

## Acceptance Criteria
- [ ] TaxAssistant Portal web application is deployed and accessible
- [ ] Dashboard displays total active users with accurate count
- [ ] New user acquisition metrics (day/month/year) match database records
- [ ] DAU and MAU calculations are correct
- [ ] Customer segmentation data is accurate by type
- [ ] All charts render correctly and are interactive
- [ ] Hourly data refresh works without errors
- [ ] Users can filter data by date range
- [ ] Export to CSV functionality works
- [ ] Dashboard loads in < 3 seconds
- [ ] Authentication/login system is working
- [ ] Database queries are optimized and don't impact system performance
- [ ] All metrics tested with actual data from production database
- [ ] Portal structure supports adding future features (monitoring, configuration)

## Implementation Notes
- Design portal with modular architecture to allow adding new features/pages
- Create main navigation/sidebar for future features
- Identify and use existing database tables for customers and activities
- Consider creating a  table to store hourly aggregates (improves performance)
- Implement proper database indexing on frequently queried columns
- Add data validation to ensure accuracy
- Consider pagination for large datasets
- Set up CI/CD pipeline for portal deployment
