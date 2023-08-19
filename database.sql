use db;

CREATE TABLE users(
    user_id varchar(20) NOT NULL
    username varchar(32) NOT NULL,
    avatar varchar(105) NOT NULL,
    PRIMARY KEY (user_id)
);
