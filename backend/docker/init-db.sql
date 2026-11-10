-- Application role: not the table owner and without BYPASSRLS, so Row-Level Security applies.
CREATE ROLE sdt_app LOGIN PASSWORD 'sdt_app';
CREATE DATABASE sdtreasury_test OWNER sdtreasury;
