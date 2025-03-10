// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

contract RideChain is ReentrancyGuard {
    using ECDSA for bytes32;

    IERC20 public immutable RIDE;
    address public immutable publicGoodFund;

    struct Ride {
        address rider;
        address driver;
        uint64 startTime;
        uint64 endTime;
        uint120 amount;
        uint8 status; // 0 = pending, 1 = completed, 2 = reversed
    }

    mapping(bytes32 => Ride) public rides;
    mapping(address => uint8) public failedReversals;
    mapping(bytes32 => bool) public commitments;

    event RideStarted(bytes32 indexed rideId, address rider, address driver, uint120 amount);
    event RideFinalized(bytes32 indexed rideId, address driver, uint120 payout);
    event RideReversed(bytes32 indexed rideId, address rider, uint120 refund, uint120 penalty);
    event EmergencyRelease(bytes32 indexed rideId, uint120 penalty);

    constructor(address _rideToken, address _publicGoodFund) {
        RIDE = IERC20(_rideToken);
        publicGoodFund = _publicGoodFund;
    }

    function startRide(
        address _driver,
        uint120 _amount,
        uint64 _startTime,
        bytes32 _commitment
    ) external nonReentrant {
        require(_driver != address(0), "Invalid driver");
        require(commitments[_commitment], "Commitment not registered");

        bytes32 rideId = keccak256(abi.encodePacked(msg.sender, _driver, _startTime));
        require(rides[rideId].rider == address(0), "Ride already exists");

        rides[rideId] = Ride(msg.sender, _driver, _startTime, 0, _amount, 0);
        RIDE.transferFrom(msg.sender, address(this), _amount);

        emit RideStarted(rideId, msg.sender, _driver, _amount);
    }

    function finalizeRide(bytes32 rideId) external nonReentrant {
        Ride storage ride = rides[rideId];
        require(ride.status == 0, "Ride already finalized/reversed");
        require(msg.sender == ride.driver, "Only driver can finalize");

        ride.endTime = uint64(block.timestamp);
        ride.status = 1;
        RIDE.transfer(ride.driver, ride.amount);

        emit RideFinalized(rideId, ride.driver, ride.amount);
    }

    function reverseRide(bytes32 rideId) external nonReentrant {
        Ride storage ride = rides[rideId];
        require(ride.status == 0, "Ride already finalized/reversed");
        require(msg.sender == ride.rider, "Only rider can reverse");
        require(block.timestamp <= ride.startTime + 12 minutes, "Reversal time expired");

        uint120 penalty = ride.amount / 10; // 10% penalty
        uint120 refund = ride.amount - penalty;

        ride.status = 2;
        RIDE.transfer(ride.rider, refund);
        RIDE.transfer(publicGoodFund, penalty);

        failedReversals[msg.sender]++;
        if (failedReversals[msg.sender] >= 3) {
            revert("Too many failed reversals, 24-hour lockout");
        }

        emit RideReversed(rideId, ride.rider, refund, penalty);
    }

    function emergencyRelease(bytes32 rideId) external {
        require(tx.gasprice > 100 gwei, "Gas price too low");
        Ride storage ride = rides[rideId];
        require(ride.status == 0, "Ride already finalized/reversed");

        uint120 penalty = ride.amount / 10;
        ride.status = 2;
        RIDE.transfer(publicGoodFund, penalty);

        emit EmergencyRelease(rideId, penalty);
    }

    function registerCommitment(bytes32 commitment) external {
        commitments[commitment] = true;
    }
}

